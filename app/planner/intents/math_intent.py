import re

from app.enums.action_type import ActionType
from app.models.plan import Plan
from app.planner.intents.base_intent import BaseIntent


class MathIntent(BaseIntent):
    """
    Detects mathematical expressions.
    """

    def matches(
        self,
        prompt: str,
    ) -> bool:
        """
        Determine whether the prompt contains
        a mathematical expression.
        """

        prompt = prompt.lower().strip()

        if re.fullmatch(
            r"[0-9+\-*/(). ]+",
            prompt,
        ):
            return True

        return bool(
            re.search(
                r"\d+\s*[\+\-\*/]\s*\d+",
                prompt,
            )
        )

    def create_plan(
        self,
        prompt: str,
    ) -> Plan:
        """
        Create a calculator execution plan.
        """

        match = re.search(
            r"\d+\s*[\+\-\*/]\s*\d+",
            prompt,
        )

        expression = match.group() if match else prompt.strip()

        return Plan(
            action=ActionType.TOOL,
            tool="calculator",
            args={
                "expression": expression,
            },
        )