from abc import ABC, abstractmethod

from app.models.plan import Plan
from app.planner.models import IntentMatch


class BaseIntent(ABC):
    """
    Base class for all planner intents.
    """

    @abstractmethod
    def matches(
        self,
        prompt: str,
    ) -> IntentMatch:
        """
        Determine whether this intent matches the prompt.
        """
        pass

    @abstractmethod
    def create_plan(
        self,
        prompt: str,
    ) -> Plan:
        """
        Build and return an execution plan.
        """
        pass