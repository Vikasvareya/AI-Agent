from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass(frozen=True)
class WorkflowEvent:
    run_id: str
    event_type: str
    payload: dict
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class AgentActivityEvent:
    run_id: str
    conversation_id: str
    event_type: str
    status: str
    summary: str
    sequence_number: int
    visibility: str = "user"
    task_id: str | None = None
    agent_id: str | None = None
    parent_task_id: str | None = None
    metadata: dict = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "run_id": self.run_id,
            "conversation_id": self.conversation_id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "parent_task_id": self.parent_task_id,
            "event_type": self.event_type,
            "status": self.status,
            "summary": self.summary,
            "timestamp": self.timestamp,
            "sequence_number": self.sequence_number,
            "visibility": self.visibility,
            "metadata": self.metadata,
        }
