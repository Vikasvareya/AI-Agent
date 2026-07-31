import re

from app.enums.action_type import ActionType
from app.models.plan import Plan
from app.planner.intents.base_intent import BaseIntent
from app.planner.models import IntentMatch


class MathIntent(BaseIntent):
    """
    Detects mathematical expressions.
    """

    def matches(
        self,
        prompt: str,
    ) -> IntentMatch:
        """
        Determine whether the prompt contains
        a mathematical expression.
        """

        prompt = prompt.lower().strip()

        matched = False

        if re.fullmatch(
            r"[0-9+\-*/(). ]+",
            prompt,
        ):
            matched = True

        elif re.search(
            r"\d+\s*[\+\-\*/]\s*\d+",
            prompt,
        ):
            matched = True

        return IntentMatch(
            matched=matched,
            confidence=0.95 if matched else 0.0,
            priority=100,
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