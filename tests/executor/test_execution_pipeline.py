from app.enums.action_type import ActionType
from app.executor.action_registry import ActionRegistry
from app.executor.executor import Executor
from app.executor.handlers.base_handler import BaseHandler
from app.models.plan import Plan
from app.planner.enums import PlanStatus, StepStatus
from app.planner.execution_context import ExecutionContext
from app.planner.execution_plan import ExecutionPlan
from app.planner.execution_step import ExecutionStep


class EchoHandler(BaseHandler):
    def execute(self, plan: Plan) -> str:
        return str(plan.args["value"])


def test_executes_dependent_steps_and_resolves_previous_result():
    registry = ActionRegistry()
    registry.register(ActionType.TOOL, EchoHandler())

    first = ExecutionStep(
        action=ActionType.TOOL,
        args={"tool": "echo", "value": "first"},
    )
    second = ExecutionStep(
        action=ActionType.TOOL,
        args={"tool": "echo", "value": "{{previous}}"},
        dependencies=[first.id],
    )
    plan = ExecutionPlan(
        goal="Chain two steps",
        steps=[first, second],
    )

    result = Executor(registry).execute(plan)

    assert result == "first"
    assert plan.status is PlanStatus.COMPLETED
    assert first.status is StepStatus.COMPLETED
    assert second.status is StepStatus.COMPLETED
    assert second.result == "first"


def test_execution_context_stores_results():
    registry = ActionRegistry()
    registry.register(ActionType.TOOL, EchoHandler())
    context = ExecutionContext()

    first = ExecutionStep(
        action=ActionType.TOOL,
        args={"tool": "echo", "value": "value"},
    )
    second = ExecutionStep(
        action=ActionType.TOOL,
        args={"tool": "echo", "value": "{{first-reference}}"},
        dependencies=[first.id],
    )
    context.results["first-reference"] = "resolved"
    plan = ExecutionPlan(
        goal="Use context",
        steps=[first, second],
    )

    result = Executor(registry).execute(plan, context)

    assert result == "resolved"
    assert context.results[first.id] == "value"


def test_unknown_dependency_fails_validation():
    registry = ActionRegistry()
    plan = ExecutionPlan(
        goal="Invalid plan",
        steps=[
            ExecutionStep(
                action=ActionType.TOOL,
                dependencies=["missing-step"],
            )
        ],
    )

    try:
        Executor(registry).execute(plan)
        assert False, "Expected unknown dependency to raise"
    except ValueError as exc:
        assert "unknown step" in str(exc)

    assert plan.status is PlanStatus.FAILED


def test_legacy_plan_execution_is_preserved():
    registry = ActionRegistry()
    registry.register(ActionType.TOOL, EchoHandler())
    legacy_plan = Plan(
        action=ActionType.TOOL,
        tool="echo",
        args={"value": "legacy"},
    )

    result = Executor(registry).execute(legacy_plan)

    assert result == "legacy"
