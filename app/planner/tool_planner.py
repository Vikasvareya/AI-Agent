from app.enums.action_type import ActionType
from app.models.plan import Plan
from app.planner.base_planner import BasePlanner
from app.planner.intents.registry import IntentRegistry
from app.planner.intents.base_intent import BaseIntent

class ToolPlanner(BasePlanner):
    """
    Planner responsible for selecting
    the appropriate intent.
    """

    def __init__(
        self,
        registry: IntentRegistry,
    ):
        self.registry = registry

    def plan(
        self,
        prompt: str,
    ) -> Plan:
        """
        Determine the next action.
        """

        intent: BaseIntent | None = self.registry.get_matching_intent(
            prompt,
        )

        if intent is None:
            print("[Planner] No intent selected. Falling back to CHAT.")

            return Plan(
                action=ActionType.CHAT,
            )

        print(f"[Planner] Selected: {intent.__class__.__name__}")

        return intent.create_plan(prompt)