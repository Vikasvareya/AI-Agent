from abc import ABC, abstractmethod
from app.planner.execution_plan import ExecutionPlan

from app.models.plan import Plan


class BaseExecutor(ABC):
    """
    Base Executor contract.
    """

    @abstractmethod
    def execute(
        self,
        plan: Plan | ExecutionPlan,
    ) -> str:
        """
        Execute a plan.
        """
        pass