from dataclasses import dataclass, field
from uuid import uuid4

from app.enums.action_type import ActionType
from app.planner.enums import StepStatus


@dataclass
class ExecutionStep:
    """
    Represents a single executable step
    inside an execution plan.
    """

    action: ActionType

    args: dict = field(default_factory=dict)

    id: str = field(
        default_factory=lambda: str(uuid4())
    )

    status: StepStatus = StepStatus.PENDING

    dependencies: list[str] = field(
        default_factory=list
    )

    result: object | None = None