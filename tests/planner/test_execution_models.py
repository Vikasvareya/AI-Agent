from app.enums.action_type import ActionType
from app.planner.enums import PlanStatus, StepStatus
from app.planner.execution_context import ExecutionContext
from app.planner.execution_plan import ExecutionPlan
from app.planner.execution_step import ExecutionStep


def test_execution_step_defaults():
    step = ExecutionStep(
        action=ActionType.TOOL,
    )

    assert step.id
    assert step.action is ActionType.TOOL
    assert step.status is StepStatus.PENDING
    assert step.args == {}
    assert step.dependencies == []
    assert step.result is None


def test_execution_step_with_arguments():
    step = ExecutionStep(
        action=ActionType.TOOL,
        args={
            "tool": "calculator",
            "expression": "2+2",
        },
    )

    assert step.args["tool"] == "calculator"
    assert step.args["expression"] == "2+2"


def test_execution_step_ids_are_unique():
    first = ExecutionStep(
        action=ActionType.TOOL,
    )

    second = ExecutionStep(
        action=ActionType.TOOL,
    )

    assert first.id != second.id


def test_execution_plan_defaults():
    plan = ExecutionPlan(
        goal="Calculate 2+2",
    )

    assert plan.id
    assert plan.goal == "Calculate 2+2"
    assert plan.steps == []
    assert plan.status is PlanStatus.PENDING
    assert plan.metadata == {}


def test_execution_plan_contains_steps():
    step = ExecutionStep(
        action=ActionType.TOOL,
        args={
            "tool": "calculator",
            "expression": "2+2",
        },
    )

    plan = ExecutionPlan(
        goal="Calculate 2+2",
        steps=[step],
    )

    assert len(plan.steps) == 1
    assert plan.steps[0] is step


def test_execution_context_defaults():
    context = ExecutionContext()

    assert context.variables == {}
    assert context.results == {}
    assert context.metadata == {}


def test_execution_context_stores_runtime_data():
    context = ExecutionContext()

    context.variables["user"] = "Vikas"
    context.results["step-1"] = 4
    context.metadata["request_id"] = "test-request"

    assert context.variables["user"] == "Vikas"
    assert context.results["step-1"] == 4
    assert context.metadata["request_id"] == "test-request"


def test_execution_context_isolated_between_instances():
    first = ExecutionContext()
    second = ExecutionContext()

    first.variables["value"] = 10

    assert "value" not in second.variables