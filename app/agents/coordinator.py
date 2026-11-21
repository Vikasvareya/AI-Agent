from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from app.agents.agent_registry import AgentRegistry
from app.agents.shared_memory import SharedMemory


@dataclass
class DelegationMessage:
    id: str
    task_id: str
    sender: str
    recipient: str
    content: str
    created_at: str


@dataclass
class DelegationTask:
    id: str
    owner_id: str
    requester_role: str
    agent_name: str
    prompt: str
    status: str = "pending"
    result: str | None = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DelegationPermissionPolicy:
    def __init__(self, allowed_agents: dict[str, tuple[str, ...] | None]):
        self.allowed_agents = allowed_agents

    def is_allowed(self, role: str, agent_name: str) -> bool:
        allowed = self.allowed_agents.get(role)
        if allowed is None:
            return role == "admin"
        return agent_name in allowed


class CoordinatorAgent:
    def __init__(
        self,
        registry: AgentRegistry,
        shared_memory: SharedMemory,
        default_agent: str,
    ):
        self.registry = registry
        self.shared_memory = shared_memory
        self.default_agent = default_agent

    def route(self, prompt: str, *, agent_name: str | None = None) -> str:
        target_name = agent_name or self._match_agent(prompt) or self.default_agent
        target = self.registry.get(target_name)
        if target is None:
            raise ValueError(f"No agent registered as '{target_name}'.")

        self.shared_memory.publish("coordinator", target_name, prompt)
        result = target.chat(prompt)
        self.shared_memory.set(f"result:{target_name}", result)
        self.shared_memory.publish(target_name, "coordinator", result)
        return result

    def chat(self, prompt: str) -> str:
        return self.route(prompt)

    def enqueue(
        self,
        owner_id: str,
        requester_role: str,
        agent_names: list[str],
        prompt: str,
        *,
        policy: "DelegationPermissionPolicy | None" = None,
        persistence_store=None,
    ) -> dict:
        if persistence_store is None:
            raise ValueError("Durable delegation requires a persistence store.")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("A non-empty delegation prompt is required.")
        if not agent_names:
            raise ValueError("At least one agent name is required.")
        names = list(dict.fromkeys(agent_names))
        if len(names) > 16:
            raise ValueError("At most 16 agents can be delegated in one request.")
        policy = policy or DelegationPermissionPolicy({
            "admin": None,
            "user": ("echo",),
        })
        denied = [name for name in names if not policy.is_allowed(requester_role, name)]
        if denied:
            raise PermissionError(
                f"Permission denied for delegated agents: {', '.join(denied)}"
            )

        tasks = []
        for name in names:
            task = DelegationTask(
                id=str(uuid4()),
                owner_id=owner_id,
                requester_role=requester_role,
                agent_name=name,
                prompt=prompt.strip(),
            )
            if self.registry.get(name) is None:
                task.status = "failed"
                task.error = f"No agent registered as '{name}'."
            persistence_store.enqueue_delegation_task(task.__dict__)
            persistence_store.save_delegation_message(
                {
                    "id": str(uuid4()),
                    "task_id": task.id,
                    "sender": "coordinator",
                    "recipient": name,
                    "content": prompt.strip(),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            tasks.append(task)
        return {
            "aggregation": {
                "status": "pending",
                "completed": 0,
                "failed": 0,
                "results": [
                    {
                        "agent": task.agent_name,
                        "task_id": task.id,
                        "status": task.status,
                        "result": None,
                        "error": task.error,
                    }
                    for task in tasks
                ],
            },
            "tasks": [task.__dict__ for task in tasks],
        }

    def _match_agent(self, prompt: str) -> str | None:
        normalized = prompt.lower()
        for name in self.registry.names():
            if name.lower() in normalized:
                return name
        return None

    def delegate(
        self,
        owner_id: str,
        requester_role: str,
        agent_names: list[str],
        prompt: str,
        *,
        policy: "DelegationPermissionPolicy | None" = None,
        persistence_store=None,
        max_parallel: int = 8,
    ) -> dict:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("A non-empty delegation prompt is required.")
        if not agent_names:
            raise ValueError("At least one agent name is required.")
        names = list(dict.fromkeys(agent_names))
        if len(names) > 16:
            raise ValueError("At most 16 agents can be delegated in one request.")
        policy = policy or DelegationPermissionPolicy({
            "admin": None,
            "user": ("echo",),
        })
        denied = [name for name in names if not policy.is_allowed(requester_role, name)]
        if denied:
            raise PermissionError(
                f"Permission denied for delegated agents: {', '.join(denied)}"
            )

        tasks = []
        for name in names:
            task = DelegationTask(
                id=str(uuid4()),
                owner_id=owner_id,
                requester_role=requester_role,
                agent_name=name,
                prompt=prompt.strip(),
            )
            if self.registry.get(name) is None:
                task.status = "failed"
                task.error = f"No agent registered as '{name}'."
            tasks.append(task)
            if persistence_store is not None:
                persistence_store.save_delegation_task(task.__dict__)
                persistence_store.save_delegation_message(
                    {
                        "id": str(uuid4()),
                        "task_id": task.id,
                        "sender": "coordinator",
                        "recipient": name,
                        "content": prompt.strip(),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                )

        def execute(task: DelegationTask) -> DelegationTask:
            if task.status == "failed":
                return task
            target = self.registry.get(task.agent_name)
            task.status = "running"
            task.updated_at = datetime.now(timezone.utc).isoformat()
            if persistence_store is not None:
                persistence_store.save_delegation_task(task.__dict__)
            try:
                task.result = target.chat(prompt.strip())
                task.status = "completed"
            except Exception as exc:
                task.error = str(exc)
                task.status = "failed"
            task.updated_at = datetime.now(timezone.utc).isoformat()
            if persistence_store is not None:
                persistence_store.save_delegation_task(task.__dict__)
                persistence_store.save_delegation_message(
                    {
                        "id": str(uuid4()),
                        "task_id": task.id,
                        "sender": task.agent_name,
                        "recipient": "coordinator",
                        "content": task.result if task.result is not None else task.error or "",
                        "created_at": task.updated_at,
                    }
                )
                self.shared_memory.publish(
                    task.agent_name,
                    "coordinator",
                    task.result if task.result is not None else task.error or "",
                )
            return task

        runnable = [task for task in tasks if task.status != "failed"]
        with ThreadPoolExecutor(
            max_workers=max(1, min(max_parallel, len(runnable) or 1))
        ) as executor:
            futures = [executor.submit(execute, task) for task in runnable]
            for future in as_completed(futures):
                future.result()

        completed = [task for task in tasks if task.status == "completed"]
        failed = [task for task in tasks if task.status == "failed"]
        return {
            "aggregation": {
                "status": "completed" if not failed else (
                    "partial" if completed else "failed"
                ),
                "completed": len(completed),
                "failed": len(failed),
                "results": [
                    {
                        "agent": task.agent_name,
                        "task_id": task.id,
                        "status": task.status,
                        "result": task.result,
                        "error": task.error,
                    }
                    for task in tasks
                ],
            },
            "tasks": [task.__dict__ for task in tasks],
        }
