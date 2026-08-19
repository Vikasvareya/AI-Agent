from enum import Enum


class StepStatus(Enum):
    """
    Represents the lifecycle state of an execution step.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PlanStatus(Enum):
    """
    Represents the lifecycle state of an execution plan.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"