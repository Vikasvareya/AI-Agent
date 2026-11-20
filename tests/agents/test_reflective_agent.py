from app.agents.reflective_agent import ReflectiveAgent
from app.context.base_context_resolver import BaseContextResolver
from app.executor.base_executor import BaseExecutor
from app.memory.conversation_memory import ConversationMemory
from app.models.plan import Plan
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
            return "Tool failed"
        return "Corrected result"


def test_reflective_agent_retries_failed_observation():
    memory = ConversationMemory()
    executor = Executor()
    agent = ReflectiveAgent(
        memory=memory,
        planner=Planner(),
        executor=executor,
        context_resolver=Resolver(),
        max_corrections=1,
    )

    result, trace = agent.run("Recover")

    assert result == "Corrected result"
    assert executor.calls == 2
    assert len(trace.reflections) == 2
    assert trace.reflections[0].corrected is False
    assert trace.reflections[1].corrected is True


def test_reflective_agent_chat_saves_final_result():
    memory = ConversationMemory()
    executor = Executor()
    agent = ReflectiveAgent(
        memory=memory,
        planner=Planner(),
        executor=executor,
        context_resolver=Resolver(),
    )

    result = agent.chat("Hello")

    assert result == "Corrected result"
    assert memory.load()[-2:] == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Corrected result"},
    ]
