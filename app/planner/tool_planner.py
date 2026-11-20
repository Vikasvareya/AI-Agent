from app.enums.action_type import ActionType
from app.models.plan import Plan
from app.planner.base_planner import BasePlanner
from app.planner.intents.registry import IntentRegistry
from app.planner.intents.base_intent import BaseIntent
from app.planner.execution_plan import ExecutionPlan
from app.planner.execution_step import ExecutionStep

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
    ) -> Plan | ExecutionPlan:
        """
        Determine the next action.
        """

        intent: BaseIntent | None = self.registry.get_matching_intent(
            prompt,
        )

        if intent is None:
            print("[Planner] No intent selected. Falling back to CHAT.")

            plan = Plan(
                action=ActionType.CHAT,
            )
        else:
            print(f"[Planner] Selected: {intent.__class__.__name__}")
            plan = intent.create_plan(prompt)

        step = ExecutionStep(
            action=plan.action,
            args={
                **plan.args,
                **(
                    {"tool": plan.tool}
                    if plan.tool is not None
                    else {}
                ),
            },
        )

        return ExecutionPlan(
            goal=prompt,
            steps=[step],
        )