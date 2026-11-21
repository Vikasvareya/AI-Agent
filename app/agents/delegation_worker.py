from datetime import datetime, timezone
from threading import Event, Thread
from uuid import uuid4

from app.agents.coordinator import CoordinatorAgent


class DelegationWorker:
    def __init__(
        self,
        coordinator: CoordinatorAgent,
        store,
        *,
        worker_id: str | None = None,
        poll_seconds: float = 0.1,
        lease_seconds: int = 60,
    ):
        self.coordinator = coordinator
        self.store = store
        self.worker_id = worker_id or f"worker-{uuid4()}"
        self.poll_seconds = max(0.05, poll_seconds)
        self.lease_seconds = max(1, lease_seconds)
        self._stop = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = Thread(
            target=self.run,
            name=f"delegation-worker-{self.worker_id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        while not self._stop.is_set():
            self.store.recover_stale_delegation_tasks()
            task = self.store.lease_delegation_task(
                self.worker_id,
                lease_seconds=self.lease_seconds,
            )
            if task is None:
                self._stop.wait(self.poll_seconds)
                continue
            target = self.coordinator.registry.get(task["agent_name"])
            if target is None:
                self.store.complete_delegation_task(
                    task["id"],
                    self.worker_id,
                    result=None,
                    error=f"No agent registered as '{task['agent_name']}'.",
                )
                continue
            heartbeat_stop = Event()
            def heartbeat():
                interval = max(0.1, self.lease_seconds / 3)
                while not heartbeat_stop.is_set():
                    if not heartbeat_stop.wait(interval):
                        self.store.renew_delegation_lease(
                            task["id"],
                            self.worker_id,
                            lease_seconds=self.lease_seconds,
                        )
            heartbeat_thread = Thread(
                target=heartbeat,
                name=f"delegation-heartbeat-{task['id']}",
                daemon=True,
            )
            heartbeat_thread.start()
            try:
                result = target.chat(task["prompt"])
                completed = self.store.complete_delegation_task(
                    task["id"],
                    self.worker_id,
                    result=result,
                    error=None,
                )
                if completed:
                    self.store.save_delegation_message(
                        {
                            "id": str(uuid4()),
                            "task_id": task["id"],
                            "sender": task["agent_name"],
                            "recipient": "coordinator",
                            "content": result,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )
            except Exception as exc:
                self.store.retry_delegation_task(
                    task["id"],
                    self.worker_id,
                    error=str(exc),
                )
            finally:
                heartbeat_stop.set()
