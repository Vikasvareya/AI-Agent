from app.agents.react_agent import ReActAgent
from app.context.base_context_resolver import BaseContextResolver
from app.executor.base_executor import BaseExecutor
from app.memory.conversation_memory import ConversationMemory
from app.models.plan import Plan
from app.planner.execution_plan import ExecutionPlan
from app.planner.execution_step import ExecutionStep
from app.enums.action_type import ActionType
from app.planner.base_planner import BasePlanner


class Resolver(BaseContextResolver):
    def resolve(self, prompt: str) -> str:
        return prompt


class Planner(BasePlanner):
    def plan(self, prompt: str) -> Plan:
        return Plan(action=ActionType.CHAT)


class Executor(BaseExecutor):
    def __init__(self):
        self.calls = 0

    def execute(self, plan: Plan, context=None) -> str:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary failure")
        return "recovered"


def test_react_agent_retries_and_records_trace():
    memory = ConversationMemory()
    executor = Executor()
    agent = ReActAgent(
        memory=memory,
        planner=Planner(),
        executor=executor,
        context_resolver=Resolver(),
        max_retries=1,
    )

    response, trace = agent.run("Answer this")

    assert response == "recovered"
    assert executor.calls == 2
    assert trace.goal == "Answer this"
    assert len(trace.steps) == 2
    assert "temporary failure" in trace.steps[0].observation
    assert trace.steps[1].observation == "recovered"


def test_react_agent_chat_saves_conversation():
    memory = ConversationMemory()
    executor = Executor()
    agent = ReActAgent(
        memory=memory,
        planner=Planner(),
        executor=executor,
        context_resolver=Resolver(),
        max_retries=1,
    )
    executor.calls = 0

    response = agent.chat("Hello")

    assert response == "recovered"
    assert memory.load()[-2:] == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "recovered"},
    ]


def test_react_execution_plan_failure_is_not_automatically_replayed():
    class FailingExecutor(BaseExecutor):
        def __init__(self):
            self.calls = 0

        def execute(self, plan, context=None):
            self.calls += 1
            raise RuntimeError("execution plan failed")

    class ExecutionPlanner(BasePlanner):
        def plan(self, prompt):
            return ExecutionPlan(
                goal=prompt,
                steps=[
                    ExecutionStep(
                        id="step",
                        action=ActionType.TOOL,
                    )
                ],
            )

    executor = FailingExecutor()
    agent = ReActAgent(
        memory=ConversationMemory(),
        planner=ExecutionPlanner(),
        executor=executor,
        context_resolver=Resolver(),
        max_retries=3,
    )

    try:
        agent.run("Do not retry")
        assert False, "Expected ExecutionPlan failure"
    except RuntimeError as exc:
        assert "execution plan failed" in str(exc)

    assert executor.calls == 1
