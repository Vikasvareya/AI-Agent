from app.enums.action_type import ActionType
from app.models.plan import Plan
from app.planner.base_planner import BasePlanner
from app.planner.intents.registry import IntentRegistry


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

        intent = self.registry.get_matching_intent(
            prompt,
        )

        if intent:
            print(f"[Planner] Selected: {intent.__class__.__name__}")
        else:
            print("[Planner] No intent selected. Falling back to CHAT.")

        if intent:
            return intent.create_plan(
                prompt,
            )

        return Plan(
            action=ActionType.CHAT,
        )