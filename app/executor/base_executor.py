from abc import ABC, abstractmethod

from app.models.plan import Plan


class BaseExecutor(ABC):
    """
    Base Executor contract.
    """

    @abstractmethod
    def execute(
        self,
        plan: Plan,
    ) -> str:
        """
        Execute a plan.
        """
        pass