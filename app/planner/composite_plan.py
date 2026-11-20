from app.enums.action_type import ActionType
from app.planner.execution_plan import ExecutionPlan
from app.planner.execution_step import ExecutionStep
from app.planner.planning_graph import PlanningGraph


class CompositePlanBuilder:
    """
    Builds ordered execution plans from reusable steps.
    """

    def __init__(
        self,
        goal: str,
    ):
        self.plan = ExecutionPlan(
            goal=goal,
        )

    def add_step(
        self,
        action: ActionType,
        *,
        args: dict | None = None,
        dependencies: list[str] | None = None,
        depends_on_previous: bool = False,
    ) -> ExecutionStep:
        step = ExecutionStep(
            action=action,
            args=args or {},
            dependencies=dependencies or [],
        )

        self.plan.add_step(
            step,
            depends_on_previous=depends_on_previous,
        )
        return step

    def add_tool_step(
        self,
        tool: str,
        args: dict | None = None,
        *,
        dependencies: list[str] | None = None,
        depends_on_previous: bool = False,
    ) -> ExecutionStep:
        tool_args = dict(args or {})
        tool_args["tool"] = tool

        return self.add_step(
            ActionType.TOOL,
            args=tool_args,
            dependencies=dependencies,
            depends_on_previous=depends_on_previous,
        )

    def add_chat_step(
        self,
        args: dict | None = None,
        *,
        dependencies: list[str] | None = None,
        depends_on_previous: bool = False,
    ) -> ExecutionStep:
        return self.add_step(
            ActionType.CHAT,
            args=args,
            dependencies=dependencies,
            depends_on_previous=depends_on_previous,
        )

    def build(self) -> ExecutionPlan:
        PlanningGraph(
            self.plan,
        ).validate()
        return self.plan
