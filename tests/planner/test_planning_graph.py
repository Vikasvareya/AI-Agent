import pytest

from app.enums.action_type import ActionType
from app.planner.composite_plan import CompositePlanBuilder
from app.planner.execution_plan import ExecutionPlan
from app.planner.execution_step import ExecutionStep
from app.planner.planning_graph import PlanningGraph


def test_graph_returns_parallel_topological_levels():
    builder = CompositePlanBuilder(
        goal="Parallel graph",
    )
    first = builder.add_tool_step("echo", {"value": "first"})
    second = builder.add_tool_step("echo", {"value": "second"})
    builder.add_tool_step(
        "echo",
        {"value": "{{previous}}"},
        dependencies=[first.id, second.id],
    )

    levels = PlanningGraph(
        builder.build(),
    ).topological_levels()

    assert len(levels) == 2
    assert levels[0] == [first, second]
    assert len(levels[1]) == 1


def test_graph_reports_unknown_dependency():
    step = ExecutionStep(
        action=ActionType.TOOL,
        dependencies=["missing"],
    )
    graph = PlanningGraph(
        ExecutionPlan(
            goal="Invalid",
            steps=[step],
        )
    )

    with pytest.raises(ValueError, match="unknown dependencies"):
        graph.validate()


def test_graph_reports_cycle():
    first = ExecutionStep(
        action=ActionType.TOOL,
    )
    second = ExecutionStep(
        action=ActionType.TOOL,
        dependencies=[first.id],
    )
    first.dependencies.append(second.id)
    graph = PlanningGraph(
        ExecutionPlan(
            goal="Cycle",
            steps=[first, second],
        )
    )

    with pytest.raises(ValueError, match="dependency cycle"):
        graph.validate()


def test_graph_returns_predecessors_and_successors():
    builder = CompositePlanBuilder(goal="Relationships")
    first = builder.add_tool_step("echo", {"value": "first"})
    second = builder.add_tool_step(
        "echo",
        {"value": "second"},
        depends_on_previous=True,
    )
    graph = PlanningGraph(builder.build())

    assert graph.predecessors(second.id) == [first]
    assert graph.successors(first.id) == [second]


def test_graph_rejects_duplicate_step_ids_before_lookup():
    first = ExecutionStep(id="same", action=ActionType.TOOL)
    second = ExecutionStep(id="same", action=ActionType.TOOL)
    graph = PlanningGraph(
        ExecutionPlan(goal="Duplicate", steps=[first, second])
    )

    with pytest.raises(ValueError, match="Duplicate step ID"):
        graph.validate()


@pytest.mark.parametrize("step_id", ["", "   ", None])
def test_graph_rejects_invalid_step_ids(step_id):
    graph = PlanningGraph(
        ExecutionPlan(
            goal="Invalid",
            steps=[ExecutionStep(id=step_id, action=ActionType.TOOL)],
        )
    )

    with pytest.raises(ValueError, match="valid non-empty step ID"):
        graph.validate()


def test_graph_rejects_self_dependency():
    step = ExecutionStep(
        id="self",
        action=ActionType.TOOL,
        dependencies=["self"],
    )
    graph = PlanningGraph(
        ExecutionPlan(goal="Self", steps=[step])
    )

    with pytest.raises(ValueError, match="cannot depend on itself"):
        graph.validate()
