from app.agents.agent_registry import AgentRegistry
from app.agents.coordinator import (
    CoordinatorAgent,
    DelegationPermissionPolicy,
)
from app.agents.shared_memory import SharedMemory


class EchoAgent:
    def __init__(self):
        self.prompts: list[str] = []

    def chat(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return f"echo:{prompt}"


def test_registry_registers_and_rejects_duplicate_names():
    registry = AgentRegistry()
    agent = EchoAgent()
    registry.register("echo", agent)

    assert registry.get("echo") is agent
    assert registry.names() == ["echo"]

    try:
        registry.register("echo", agent)
        assert False, "Expected duplicate registration to raise"
    except ValueError as exc:
        assert "already registered" in str(exc)


def test_coordinator_delegates_and_records_shared_state():
    registry = AgentRegistry()
    echo = EchoAgent()
    registry.register("echo", echo)
    shared = SharedMemory()
    coordinator = CoordinatorAgent(registry, shared, "echo")

    result = coordinator.route("Ask echo a question")

    assert result == "echo:Ask echo a question"
    assert echo.prompts == ["Ask echo a question"]
    assert shared.get("result:echo") == result
    assert len(shared.messages) == 2


def test_coordinator_uses_explicit_agent_name():
    registry = AgentRegistry()
    registry.register("echo", EchoAgent())
    registry.register("fallback", EchoAgent())
    shared = SharedMemory()
    coordinator = CoordinatorAgent(registry, shared, "fallback")

    assert coordinator.route("Hello", agent_name="echo") == "echo:Hello"


def test_coordinator_fanout_aggregates_results():
    registry = AgentRegistry()
    registry.register("echo", EchoAgent())
    registry.register("fallback", EchoAgent())
    coordinator = CoordinatorAgent(registry, SharedMemory(), "fallback")
    policy = DelegationPermissionPolicy({
        "user": ("echo",),
        "admin": None,
    })

    result = coordinator.delegate(
        "owner",
        "admin",
        ["echo", "missing"],
        "Review",
        policy=policy,
    )

    assert result["aggregation"]["status"] == "partial"
    assert result["aggregation"]["failed"] == 1
    assert result["aggregation"]["completed"] == 1
    assert len(result["tasks"]) == 2


def test_coordinator_permission_policy_denies_agent():
    registry = AgentRegistry()
    registry.register("echo", EchoAgent())
    coordinator = CoordinatorAgent(registry, SharedMemory(), "echo")
    policy = DelegationPermissionPolicy({"user": ("echo",)})

    try:
        coordinator.delegate(
            "owner",
            "user",
            ["other"],
            "Review",
            policy=policy,
        )
        assert False, "Expected denied delegation"
    except PermissionError:
        pass


def test_coordinator_fanout_persists_structured_tasks(tmp_path):
    registry = AgentRegistry()
    registry.register("echo", EchoAgent())
    coordinator = CoordinatorAgent(registry, SharedMemory(), "echo")
    policy = DelegationPermissionPolicy({"user": ("echo",)})
    from app.chat.store import ChatStore
    store = ChatStore(str(tmp_path / "tasks.sqlite3"))

    result = coordinator.delegate(
        "owner",
        "user",
        ["echo", "echo"],
        "Analyze",
        policy=policy,
        persistence_store=store,
    )

    assert result["aggregation"]["completed"] == 1
    task = result["tasks"][0]
    persisted = store.get_delegation_task("owner", task["id"])
    messages = store.list_delegation_messages("owner", task["id"])
    assert persisted["status"] == "completed"
    assert persisted["result"] == "echo:Analyze"
    assert [message["sender"] for message in messages] == [
        "coordinator",
        "echo",
    ]


def test_coordinator_queue_enqueues_lease_and_completes(tmp_path):
    from app.chat.store import ChatStore
    from app.agents.delegation_worker import DelegationWorker

    store = ChatStore(str(tmp_path / "queue.sqlite3"))
    registry = AgentRegistry()
    registry.register("echo", EchoAgent())
    coordinator = CoordinatorAgent(registry, SharedMemory(), "echo")

    result = coordinator.enqueue(
        "owner",
        "admin",
        ["echo"],
        "Queued",
        policy=DelegationPermissionPolicy({"admin": None}),
        persistence_store=store,
    )
    task_id = result["tasks"][0]["id"]
    task = store.lease_delegation_task("worker-1", lease_seconds=60)
    assert task["id"] == task_id
    assert task["status"] == "running"
    assert store.renew_delegation_lease(task_id, "worker-1", lease_seconds=60)
    assert store.complete_delegation_task(
        task_id,
        "worker-1",
        result="echo:Queued",
        error=None,
    )
    persisted = store.get_delegation_task("owner", task_id)
    assert persisted["status"] == "completed"
    assert persisted["result"] == "echo:Queued"


def test_queue_recovery_and_owner_cancellation(tmp_path):
    from app.chat.store import ChatStore

    store = ChatStore(str(tmp_path / "recovery.sqlite3"))
    task = {
        "id": "task-recovery",
        "owner_id": "owner",
        "requester_role": "admin",
        "agent_name": "echo",
        "prompt": "Recover",
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": "2020-01-01T00:00:00+00:00",
        "updated_at": "2020-01-01T00:00:00+00:00",
    }
    store.enqueue_delegation_task(task)
    leased = store.lease_delegation_task(
        "worker-old",
        lease_seconds=1,
    )
    assert leased["id"] == "task-recovery"
    store.lease_expires_at = None
    assert store.cancel_delegation_task("owner", "task-recovery")
    assert store.get_delegation_task("owner", "task-recovery")["status"] == "cancelled"


def test_queue_stale_lease_can_be_recovered(tmp_path):
    from app.chat.store import ChatStore

    store = ChatStore(str(tmp_path / "stale.sqlite3"))
    task = {
        "id": "task-stale",
        "owner_id": "owner",
        "requester_role": "admin",
        "agent_name": "echo",
        "prompt": "Stale",
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": "2020-01-01T00:00:00+00:00",
        "updated_at": "2020-01-01T00:00:00+00:00",
    }
    store.enqueue_delegation_task(task)
    store.lease_delegation_task("worker-old", lease_seconds=1)
    from datetime import datetime, timedelta, timezone
    expired = (
        datetime.now(timezone.utc) - timedelta(seconds=5)
    ).isoformat()
    with store._connection() as connection:
        store._execute(
            connection,
            """
            UPDATE delegation_queue
            SET lease_expires_at = ?
            WHERE task_id = ?
            """,
            (expired, "task-stale"),
        )
    assert store.recover_stale_delegation_tasks() >= 1
    re_leased = store.lease_delegation_task("worker-new", lease_seconds=60)
    assert re_leased["id"] == "task-stale"


def test_queue_execution_error_requeues_with_bounded_attempts(tmp_path):
    from app.chat.store import ChatStore

    store = ChatStore(str(tmp_path / "retry.sqlite3"))
    task = {
        "id": "task-retry",
        "owner_id": "owner",
        "requester_role": "admin",
        "agent_name": "echo",
        "prompt": "Retry",
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": "2020-01-01T00:00:00+00:00",
        "updated_at": "2020-01-01T00:00:00+00:00",
    }
    store.enqueue_delegation_task(task)
    leased = store.lease_delegation_task("worker-1", lease_seconds=60)
    assert leased["id"] == "task-retry"
    assert store.retry_delegation_task(
        "task-retry",
        "worker-1",
        error="temporary failure",
    )
    persisted = store.get_delegation_task("owner", "task-retry")
    assert persisted["status"] == "pending"
    re_leased = store.lease_delegation_task("worker-2", lease_seconds=60)
    assert re_leased["id"] == "task-retry"


def test_two_workers_cannot_duplicate_lease(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from app.chat.store import ChatStore

    store = ChatStore(str(tmp_path / "concurrent.sqlite3"))
    task = {
        "id": "task-concurrent",
        "owner_id": "owner",
        "requester_role": "admin",
        "agent_name": "echo",
        "prompt": "Only once",
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": "2020-01-01T00:00:00+00:00",
        "updated_at": "2020-01-01T00:00:00+00:00",
    }
    store.enqueue_delegation_task(task)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(store.lease_delegation_task, "worker-a", lease_seconds=60)
        second = executor.submit(store.lease_delegation_task, "worker-b", lease_seconds=60)
        leases = [first.result(), second.result()]

    claimed = [lease for lease in leases if lease is not None]
    assert len(claimed) == 1
    assert claimed[0]["id"] == "task-concurrent"


def test_worker_heartbeat_renews_a_long_running_task(tmp_path):
    import time
    from app.chat.store import ChatStore
    from app.agents.delegation_worker import DelegationWorker

    class SlowEchoAgent:
        def chat(self, prompt):
            time.sleep(0.35)
            return f"echo:{prompt}"

    store = ChatStore(str(tmp_path / "heartbeat.sqlite3"))
    registry = AgentRegistry()
    registry.register("slow", SlowEchoAgent())
    coordinator = CoordinatorAgent(registry, SharedMemory(), "slow")
    worker = DelegationWorker(
        coordinator,
        store,
        worker_id="heartbeat-worker",
        poll_seconds=0.05,
        lease_seconds=1,
    )
    task = {
        "id": "task-heartbeat",
        "owner_id": "owner",
        "requester_role": "admin",
        "agent_name": "slow",
        "prompt": "Wait",
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": "2020-01-01T00:00:00+00:00",
        "updated_at": "2020-01-01T00:00:00+00:00",
    }
    store.enqueue_delegation_task(task)
    worker.start()
    deadline = time.time() + 3
    while time.time() < deadline:
        persisted = store.get_delegation_task("owner", "task-heartbeat")
        if persisted["status"] == "completed":
            break
        time.sleep(0.05)
    worker.stop()
    assert persisted["status"] == "completed"
