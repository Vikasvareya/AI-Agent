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

    def add_step(
        self,
        step: ExecutionStep,
        *,
        depends_on_previous: bool = False,
    ) -> ExecutionStep:
        if depends_on_previous and self.steps:
            step.dependencies.append(
                self.steps[-1].id
            )

        self.steps.append(step)
        return step