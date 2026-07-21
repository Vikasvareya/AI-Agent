import re

from app.planner.base_planner import BasePlanner
from app.models.plan import Plan
from app.enums.action_type import ActionType


class ToolPlanner(BasePlanner):
    """
    Simple planner.

    Detects mathematical expressions.
    """

    def plan(
        self,
        prompt: str,
    ) -> dict:

        expression = prompt.strip()

        if re.fullmatch(
            r"[0-9+\-*/(). ]+",
            expression,
        ):
            return Plan(
            action=ActionType.TOOL,
            tool="calculator",
            args={
                "expression": expression,
            },
        )

        time_keywords = (
            "today",
            "current date",
            "current time",
            "time",
            "date",
        )

        if any(keyword in prompt.lower() for keyword in time_keywords):
            return Plan(
                action=ActionType.TOOL,
                tool="time",
            )
            
        return Plan(
            action=ActionType.CHAT,
        )