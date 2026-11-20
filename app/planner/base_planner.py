from abc import ABC, abstractmethod

from app.models.plan import Plan
from app.planner.execution_plan import ExecutionPlan


class BasePlanner(ABC):
    """
    Base class for all planners.
    """

    @abstractmethod
    def plan(
        self,
        prompt: str,
    ) -> Plan | ExecutionPlan:
        """
        Generate an execution plan for the given prompt.
        """
        pass