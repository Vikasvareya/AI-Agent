import re

from app.planner.base_planner import BasePlanner


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
            return {
                "action": "tool",
                "tool": "calculator",
                "args": {
                    "expression": expression,
                },
            }

        return {
            "action": "chat",
        }