from app.enums.action_type import ActionType
from app.planner.execution_plan import ExecutionPlan
from app.planner.execution_step import ExecutionStep
from app.planner.intents.registry import IntentRegistry
from app.planner.tool_planner import ToolPlanner


def test_tool_planner_returns_single_step_execution_plan():
    registry = IntentRegistry()
    registry.register_default_intents()
    planner = ToolPlanner(registry)

    plan = planner.plan("2 + 2")

    assert isinstance(plan, ExecutionPlan)
    assert plan.goal == "2 + 2"
    assert len(plan.steps) == 1
    assert isinstance(plan.steps[0], ExecutionStep)
    assert plan.steps[0].action is ActionType.TOOL
    assert plan.steps[0].args["tool"] == "calculator"
    assert plan.steps[0].args["expression"] == "2 + 2"


def test_tool_planner_falls_back_to_chat_execution_plan():
    registry = IntentRegistry()
    registry.register_default_intents()
    planner = ToolPlanner(registry)

    plan = planner.plan("Tell me a short story")

    assert isinstance(plan, ExecutionPlan)
    assert len(plan.steps) == 1
    assert plan.steps[0].action is ActionType.CHAT
