from app.enums.action_type import ActionType
from app.models.plan import Plan
from app.planner.intents.base_intent import BaseIntent


class TimeIntent(BaseIntent):
    """
    Detects requests related to date and time.
    """

    KEYWORDS = (
        "time",
        "date",
        "today",
        "day",
        "month",
        "year",
        "weekday",
        "current time",
        "current date",
    )

    def matches(
        self,
        prompt: str,
    ) -> bool:
        """
        Determine whether the prompt is asking
        about the current date or time.
        """

        prompt = prompt.lower()

        return any(
            keyword in prompt
            for keyword in self.KEYWORDS
        )

    def create_plan(
        self,
        prompt: str,
    ) -> Plan:
        """
        Create a time tool execution plan.
        """

        return Plan(
            action=ActionType.TOOL,
            tool="time",
            args={},
        )