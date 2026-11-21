from app.enums.action_type import ActionType
from app.planner.execution_plan import ExecutionPlan
from app.planner.execution_step import ExecutionStep
from app.planner.intents.registry import IntentRegistry
from app.planner.tool_planner import ToolPlanner
from app.planner.intents.time_intent import TimeIntent
import pytest


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


@pytest.mark.parametrize(
    "prompt",
    [
        "What time is it?",
        "What is the date today?",
        "What is today's date?",
        "What day is today?",
        "Current date?",
        "Current time?",
        "Show me today's date and time.",
        "What date is tomorrow?",
        "What date was yesterday?",
    ],
)
def test_time_intent_matches_real_date_and_time_requests(prompt):
    assert TimeIntent().matches(prompt).matched is True


@pytest.mark.parametrize(
    "prompt",
    [
        "How do I date someone?",
        "What should I learn today?",
    ],
)
def test_time_intent_avoids_unrelated_date_queries(prompt):
    assert TimeIntent().matches(prompt).matched is False


@pytest.mark.parametrize(
    ("prompt", "timezone"),
    [
        ("What time is it in London?", "Europe/London"),
        ("What time is it in Germany?", "Europe/Berlin"),
        ("What time is it in Berlin?", "Europe/Berlin"),
        ("What time is it in India?", "Asia/Kolkata"),
        ("What time is it in Tokyo?", "Asia/Tokyo"),
        ("What time is it in New York?", "America/New_York"),
        ("What time is it in California?", "America/Los_Angeles"),
        ("What time is it in UTC?", "UTC"),
    ],
)
def test_time_intent_resolves_location_timezone(prompt, timezone):
    resolved = TimeIntent().create_plan(prompt)

    assert resolved.action is ActionType.TOOL
    assert resolved.tool == "time"
    assert resolved.args["timezone"] == timezone


def test_time_intent_requests_clarification_for_ambiguous_australia():
    resolved = TimeIntent().create_plan(
        "What time is it in Australia?"
    )

    assert resolved.tool == "time"
    assert "clarification" in resolved.args
    assert "Australian city" in resolved.args["clarification"]
