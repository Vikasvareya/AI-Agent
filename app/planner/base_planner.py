from abc import ABC, abstractmethod
from app.models.plan import Plan

class BasePlanner(ABC):
    """
    Base planner responsible for deciding
    what action the AI Agent should take.
    """

    @abstractmethod
    def plan(
        self,
        prompt: str,
    ) -> Plan:
        """
        Decide the next action.

        Returns:
            A Plan object describing the next action.
        """
        pass