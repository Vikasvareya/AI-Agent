from abc import ABC, abstractmethod

from app.models.plan import Plan


class BasePlanner(ABC):
    """
    Base class for all planners.
    """

    @abstractmethod
    def plan(
        self,
        prompt: str,
    ) -> Plan:
        """
        Generate an execution plan for the given prompt.
        """
        pass