from dataclasses import dataclass, field
from enum import Enum
from typing import Callable
from uuid import uuid4


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class WorkflowNode:
    name: str
    action: Callable
    dependencies: list[str] = field(default_factory=list)
    retries: int = 0
    timeout_seconds: float | None = None
    requires_approval: bool = False


@dataclass
class Workflow:
    name: str
    nodes: list[WorkflowNode] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid4()))

    def add_node(
        self,
        node: WorkflowNode,
    ) -> "Workflow":
        if any(existing.name == node.name for existing in self.nodes):
            raise ValueError(
                f"Duplicate workflow node: '{node.name}'."
            )
        self.nodes.append(node)
        return self


@dataclass
class WorkflowRun:
    workflow_id: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    results: dict[str, object] = field(default_factory=dict)
    node_statuses: dict[str, NodeStatus] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    idempotency_key: str | None = None
    approvals: dict[str, ApprovalStatus] = field(default_factory=dict)
    approval_decisions: dict[str, str] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    owner_id: str | None = None
    initial_context: dict = field(default_factory=dict)
