from dataclasses import dataclass, field
from uuid import uuid4

from app.planner.enums import PlanStatus
from app.planner.execution_step import ExecutionStep


@dataclass
class ExecutionPlan:
    """
    Represents a complete execution plan.

    A plan contains one or more execution steps
    that can be processed by the executor.
    """

    goal: str

    id: str = field(
        default_factory=lambda: str(uuid4())
    )

    steps: list[ExecutionStep] = field(
        default_factory=list
    )

    status: PlanStatus = PlanStatus.PENDING

    metadata: dict = field(
        default_factory=dict
    )