from abc import ABC, abstractmethod

from app.models.plan import Plan
from app.planner.models import IntentMatch


class BaseIntent(ABC):

    @abstractmethod
    def matches(
        self,
        prompt: str,
    ) -> IntentMatch:
        pass

    @abstractmethod
    def create_plan(
        self,
        prompt: str,
    ) -> Plan:
        pass