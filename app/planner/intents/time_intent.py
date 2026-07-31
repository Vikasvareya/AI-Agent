from app.enums.action_type import ActionType
from app.models.plan import Plan
from app.planner.intents.base_intent import BaseIntent
from app.planner.models import IntentMatch


class TimeIntent(BaseIntent):
    """
    Detects time-related queries.
    """

    def matches(
        self,
        prompt: str,
    ) -> IntentMatch:

        prompt = prompt.lower()

        keywords = (
            "time",
            "clock",
            "current time",
            "what time",
        )

        matched = any(
            keyword in prompt
            for keyword in keywords
        )

        return IntentMatch(
            matched=matched,
            confidence=0.90 if matched else 0.0,
            priority=90,
        )

    def create_plan(
        self,
        prompt: str,
    ) -> Plan:

        return Plan(
            action=ActionType.TOOL,
            tool="time",
            args={},
        )