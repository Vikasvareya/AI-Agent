from abc import ABC, abstractmethod

from app.models.plan import Plan


class BaseHandler(ABC):
    """
    Base execution handler.
    """

    @abstractmethod
    def execute(
        self,
        plan: Plan,
    ) -> str:
        pass