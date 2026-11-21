from app.enums.action_type import ActionType
from app.executor.action_registry import ActionRegistry
from app.executor.executor import Executor
from app.executor.handlers.base_handler import BaseHandler
from app.models.plan import Plan
from app.planner.enums import PlanStatus, StepStatus
from app.planner.execution_context import ExecutionContext
from app.planner.execution_plan import ExecutionPlan
from app.planner.execution_step import ExecutionStep
import pytest


class EchoHandler(BaseHandler):
    def execute(self, plan: Plan) -> str:
        return str(plan.args["value"])


class CountingEchoHandler(BaseHandler):
    def __init__(self):
        self.calls = []

    def execute(self, plan: Plan) -> object:
        self.calls.append(plan.args)
        value = plan.args["value"]
        if value == "explode":
            raise RuntimeError("boom")
        return value


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


@pytest.mark.parametrize("step_id", ["", "   ", None])
def test_invalid_empty_step_id_is_rejected(step_id):
    registry = ActionRegistry()
    handler = CountingEchoHandler()
    registry.register(ActionType.TOOL, handler)
    step = ExecutionStep(
        id=step_id,
        action=ActionType.TOOL,
        args={"tool": "echo", "value": "never"},
    )
    plan = ExecutionPlan(goal="Invalid", steps=[step])

    with pytest.raises(ValueError, match="valid non-empty step ID"):
        Executor(registry).execute(plan)

    assert handler.calls == []
    assert plan.status is PlanStatus.FAILED


def test_duplicate_step_ids_are_rejected_without_execution():
    registry = ActionRegistry()
    handler = CountingEchoHandler()
    registry.register(ActionType.TOOL, handler)
    first = ExecutionStep(
        id="duplicate",
        action=ActionType.TOOL,
        args={"tool": "echo", "value": "first"},
    )
    second = ExecutionStep(
        id="duplicate",
        action=ActionType.TOOL,
        args={"tool": "echo", "value": "second"},
    )
    plan = ExecutionPlan(goal="Duplicate", steps=[first, second])

    with pytest.raises(ValueError, match="Duplicate step ID"):
        Executor(registry).execute(plan)

    assert handler.calls == []
    assert plan.status is PlanStatus.FAILED


def test_self_dependency_is_rejected_without_execution():
    registry = ActionRegistry()
    handler = CountingEchoHandler()
    registry.register(ActionType.TOOL, handler)
    step = ExecutionStep(
        id="self",
        action=ActionType.TOOL,
        args={"tool": "echo", "value": "never"},
        dependencies=["self"],
    )
    plan = ExecutionPlan(goal="Self", steps=[step])

    with pytest.raises(ValueError, match="cannot depend on itself"):
        Executor(registry).execute(plan)

    assert handler.calls == []
    assert plan.status is PlanStatus.FAILED


def test_circular_dependency_is_rejected_without_execution():
    registry = ActionRegistry()
    handler = CountingEchoHandler()
    registry.register(ActionType.TOOL, handler)
    first = ExecutionStep(
        id="first",
        action=ActionType.TOOL,
        args={"tool": "echo", "value": "first"},
        dependencies=["second"],
    )
    second = ExecutionStep(
        id="second",
        action=ActionType.TOOL,
        args={"tool": "echo", "value": "second"},
        dependencies=["first"],
    )
    plan = ExecutionPlan(goal="Cycle", steps=[first, second])

    with pytest.raises(ValueError, match="dependency cycle"):
        Executor(registry).execute(plan)

    assert handler.calls == []
    assert plan.status is PlanStatus.FAILED


def test_fail_fast_marks_all_pending_steps_skipped():
    registry = ActionRegistry()
    handler = CountingEchoHandler()
    registry.register(ActionType.TOOL, handler)
    first = ExecutionStep(
        id="first",
        action=ActionType.TOOL,
        args={"tool": "echo", "value": "explode"},
    )
    dependent = ExecutionStep(
        id="dependent",
        action=ActionType.TOOL,
        args={"tool": "echo", "value": "dependent"},
        dependencies=["first"],
    )
    independent = ExecutionStep(
        id="independent",
        action=ActionType.TOOL,
        args={"tool": "echo", "value": "independent"},
    )
    plan = ExecutionPlan(
        goal="Fail fast",
        steps=[first, dependent, independent],
    )

    with pytest.raises(RuntimeError, match="boom"):
        Executor(registry).execute(plan)

    assert len(handler.calls) == 1
    assert plan.status is PlanStatus.FAILED
    assert first.status is StepStatus.FAILED
    assert first.result == "boom"
    assert dependent.status is StepStatus.SKIPPED
    assert independent.status is StepStatus.SKIPPED


def test_failure_after_completed_step_preserves_completed_result():
    registry = ActionRegistry()
    handler = CountingEchoHandler()
    registry.register(ActionType.TOOL, handler)
    first = ExecutionStep(
        id="first",
        action=ActionType.TOOL,
        args={"tool": "echo", "value": "done"},
    )
    second = ExecutionStep(
        id="second",
        action=ActionType.TOOL,
        args={"tool": "echo", "value": "explode"},
        dependencies=["first"],
    )
    third = ExecutionStep(
        id="third",
        action=ActionType.TOOL,
        args={"tool": "echo", "value": "{{previous}}"},
        dependencies=["second"],
    )
    plan = ExecutionPlan(goal="Partial", steps=[first, second, third])

    with pytest.raises(RuntimeError, match="boom"):
        Executor(registry).execute(plan)

    assert first.status is StepStatus.COMPLETED
    assert first.result == "done"
    assert second.status is StepStatus.FAILED
    assert third.status is StepStatus.SKIPPED
    assert plan.status is PlanStatus.FAILED


def test_completed_plan_cannot_execute_again():
    registry = ActionRegistry()
    handler = CountingEchoHandler()
    registry.register(ActionType.TOOL, handler)
    step = ExecutionStep(
        id="once",
        action=ActionType.TOOL,
        args={"tool": "echo", "value": "side-effect"},
    )
    plan = ExecutionPlan(goal="Once", steps=[step])

    assert Executor(registry).execute(plan) == "side-effect"
    result = step.result
    with pytest.raises(ValueError, match="already completed"):
        Executor(registry).execute(plan)

    assert len(handler.calls) == 1
    assert step.status is StepStatus.COMPLETED
    assert step.result == result


def test_failed_plan_cannot_be_replayed():
    registry = ActionRegistry()
    handler = CountingEchoHandler()
    registry.register(ActionType.TOOL, handler)
    step = ExecutionStep(
        id="failed",
        action=ActionType.TOOL,
        args={"tool": "echo", "value": "explode"},
    )
    plan = ExecutionPlan(goal="Failed once", steps=[step])

    with pytest.raises(RuntimeError, match="boom"):
        Executor(registry).execute(plan)

    with pytest.raises(ValueError, match="FAILED state"):
        Executor(registry).execute(plan)

    assert len(handler.calls) == 1
    assert step.status is StepStatus.FAILED
    assert step.result == "boom"


@pytest.mark.parametrize(
    ("placeholder", "expected"),
    [
        ("{{previous}}", 42),
        ("{{ previous }}", 42),
        ("{{  previous  }}", 42),
    ],
)
def test_exact_previous_placeholder_preserves_integer_type(placeholder, expected):
    registry = ActionRegistry()
    handler = CountingEchoHandler()
    registry.register(ActionType.TOOL, handler)
    first = ExecutionStep(
        id="first",
        action=ActionType.TOOL,
        args={"tool": "echo", "value": 42},
    )
    second = ExecutionStep(
        id="second",
        action=ActionType.TOOL,
        args={"tool": "echo", "value": placeholder},
        dependencies=["first"],
    )
    plan = ExecutionPlan(goal="Types", steps=[first, second])

    # Replace echo behavior is string-based in the first test handler; use
    # a dedicated type-preserving handler for this assertion.
    class TypeHandler(BaseHandler):
        def execute(self, plan: Plan) -> object:
            return plan.args["value"]

    registry = ActionRegistry()
    registry.register(ActionType.TOOL, TypeHandler())
    assert Executor(registry).execute(plan) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Laravel information", "Laravel information"),
        ({"framework": "Laravel"}, {"framework": "Laravel"}),
        ([1, 2, 3], [1, 2, 3]),
    ],
)
def test_exact_previous_placeholder_preserves_python_type(value, expected):
    registry = ActionRegistry()

    class TypeHandler(BaseHandler):
        def execute(self, plan: Plan) -> object:
            return plan.args["value"]

    registry.register(ActionType.TOOL, TypeHandler())
    first = ExecutionStep(
        id="first",
        action=ActionType.TOOL,
        args={"tool": "echo", "value": value},
    )
    second = ExecutionStep(
        id="second",
        action=ActionType.TOOL,
        args={"tool": "echo", "value": "{{ previous }}"},
        dependencies=["first"],
    )
    plan = ExecutionPlan(goal="Typed", steps=[first, second])

    assert Executor(registry).execute(plan) == expected


def test_nested_context_and_result_references_resolve():
    registry = ActionRegistry()

    class CaptureHandler(BaseHandler):
        def execute(self, plan: Plan) -> object:
            return plan.args["values"]

    registry.register(ActionType.TOOL, CaptureHandler())
    step = ExecutionStep(
        id="nested",
        action=ActionType.TOOL,
        args={
            "tool": "capture",
            "values": {
                "variable": "{{variables.profile.name}}",
                "result": "{{results.step-1.values[1]}}",
            },
        },
    )
    context = ExecutionContext(
        variables={"profile": {"name": "Laravel"}},
        results={"step-1": {"values": ["zero", "one"]}},
    )
    plan = ExecutionPlan(goal="Nested", steps=[step])

    assert Executor(registry).execute(plan, context) == {
        "variable": "Laravel",
        "result": "one",
    }


def test_missing_and_unknown_references_raise_descriptive_errors():
    registry = ActionRegistry()

    class CaptureHandler(BaseHandler):
        def execute(self, plan: Plan) -> object:
            return plan.args["value"]

    registry.register(ActionType.TOOL, CaptureHandler())

    plan = ExecutionPlan(
        goal="Missing",
        steps=[
            ExecutionStep(
                id="first",
                action=ActionType.TOOL,
                args={"tool": "capture", "value": "{{previous}}"},
            )
        ],
    )
    with pytest.raises(ValueError, match="before any step"):
        Executor(registry).execute(plan)

    plan = ExecutionPlan(
        goal="Unknown",
        steps=[
            ExecutionStep(
                id="unknown",
                action=ActionType.TOOL,
                args={"tool": "capture", "value": "{{missing.path}}"},
            )
        ],
    )
    with pytest.raises(ValueError, match="Unknown execution reference"):
        Executor(registry).execute(plan)


def test_interpolated_reference_is_stringified():
    registry = ActionRegistry()

    class CaptureHandler(BaseHandler):
        def execute(self, plan: Plan) -> object:
            return plan.args["value"]

    registry.register(ActionType.TOOL, CaptureHandler())
    first = ExecutionStep(
        id="first",
        action=ActionType.TOOL,
        args={"tool": "capture", "value": 42},
    )
    second = ExecutionStep(
        id="second",
        action=ActionType.TOOL,
        args={
            "tool": "capture",
            "value": "Framework: {{previous}}",
        },
        dependencies=["first"],
    )
    plan = ExecutionPlan(goal="Interpolation", steps=[first, second])

    assert Executor(registry).execute(plan) == "Framework: 42"
