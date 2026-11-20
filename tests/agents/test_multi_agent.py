from app.agents.agent_registry import AgentRegistry
from app.agents.coordinator import CoordinatorAgent
from app.agents.shared_memory import SharedMemory


class EchoAgent:
    def __init__(self):
        self.prompts: list[str] = []

    def chat(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return f"echo:{prompt}"


def test_registry_registers_and_rejects_duplicate_names():
    registry = AgentRegistry()
    agent = EchoAgent()
    registry.register("echo", agent)

    assert registry.get("echo") is agent
    assert registry.names() == ["echo"]

    try:
        registry.register("echo", agent)
        assert False, "Expected duplicate registration to raise"
    except ValueError as exc:
        assert "already registered" in str(exc)


def test_coordinator_delegates_and_records_shared_state():
    registry = AgentRegistry()
    echo = EchoAgent()
    registry.register("echo", echo)
    shared = SharedMemory()
    coordinator = CoordinatorAgent(registry, shared, "echo")

    result = coordinator.route("Ask echo a question")

    assert result == "echo:Ask echo a question"
    assert echo.prompts == ["Ask echo a question"]
    assert shared.get("result:echo") == result
    assert len(shared.messages) == 2


def test_coordinator_uses_explicit_agent_name():
    registry = AgentRegistry()
    registry.register("echo", EchoAgent())
    registry.register("fallback", EchoAgent())
    shared = SharedMemory()
    coordinator = CoordinatorAgent(registry, shared, "fallback")

    assert coordinator.route("Hello", agent_name="echo") == "echo:Hello"
