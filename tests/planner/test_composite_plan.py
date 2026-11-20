from app.enums.action_type import ActionType
from app.executor.action_registry import ActionRegistry
from app.executor.executor import Executor
from app.executor.handlers.base_handler import BaseHandler
from app.models.plan import Plan
from app.planner.composite_plan import CompositePlanBuilder


class EchoHandler(BaseHandler):
    def execute(self, plan: Plan) -> str:
        return str(plan.args["value"])


def test_composite_plan_builder_chains_steps():
    builder = CompositePlanBuilder(
        goal="Calculate and inspect a value",
    )

    first = builder.add_tool_step(
        "calculator",
        {"expression": "2 + 2"},
    )
    second = builder.add_tool_step(
        "calculator",
        {"expression": "{{previous}} * 3"},
        depends_on_previous=True,
    )
    plan = builder.build()

    assert len(plan.steps) == 2
    assert plan.steps[0] is first
    assert plan.steps[1] is second
    assert second.dependencies == [first.id]
    assert second.action is ActionType.TOOL


def test_composite_plan_executes_dependency_chain():
    builder = CompositePlanBuilder(
        goal="Chain values",
    )
    builder.add_tool_step(
        "echo",
        {"value": "ready"},
    )
    builder.add_tool_step(
        "echo",
        {"value": "{{previous}}"},
        depends_on_previous=True,
    )

    registry = ActionRegistry()
    registry.register(ActionType.TOOL, EchoHandler())

    result = Executor(registry).execute(
        builder.build(),
    )

    assert result == "ready"
