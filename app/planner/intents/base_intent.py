from abc import ABC, abstractmethod

from app.models.plan import Plan


class BaseIntent(ABC):
    """
    Base class for planner intents.
    """

    @abstractmethod
    def matches(
        self,
        prompt: str,
    ) -> bool:
        """
        Return True if this intent can handle the prompt.
        """
        pass

    @abstractmethod
    def create_plan(
        self,
        prompt: str,
    ) -> Plan:
        """
        Build and return a plan.
        """
        pass