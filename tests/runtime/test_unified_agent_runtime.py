from app.providers.base_provider import BaseProvider
from app.runtime.unified_agent_runtime import UnifiedAgentRuntime
from app.tools.calculator_tool import CalculatorTool


class CountingProvider(BaseProvider):
    def __init__(self):
        self.calls = []

    @property
    def default_model(self):
        return "fake-chat"

    @property
    def provider_name(self):
        return "fake"

    def list_models(self, *, refresh=False):
        return [{"id": "fake-chat", "name": "Fake Chat", "provider": "fake"}]

    def ask(self, messages, *, model=None, timeout=None):
        self.calls.append({
            "messages": messages,
            "model": model,
        })
        return "Normal chat response."


def test_unified_runtime_executes_time_tool_without_provider_call():
    provider = CountingProvider()
    runtime = UnifiedAgentRuntime(provider)

    result = runtime.execute(
        owner_id="owner-a",
        conversation_id="conversation-a",
        content="What is the date today?",
        history=[],
    )

    assert "202" in result
    assert provider.calls == []


def test_unified_runtime_executes_calculator_without_provider_call():
    provider = CountingProvider()
    runtime = UnifiedAgentRuntime(provider)

    result = runtime.execute(
        owner_id="owner-a",
        conversation_id="conversation-a",
        content="25 * 4",
        history=[],
    )

    assert result == "100"
    assert provider.calls == []


def test_unified_runtime_uses_chat_handler_for_normal_chat_and_model():
    provider = CountingProvider()
    runtime = UnifiedAgentRuntime(provider)

    result = runtime.execute(
        owner_id="owner-a",
        conversation_id="conversation-a",
        content="Explain dependency injection.",
        history=[],
        model="fake-chat",
    )

    assert result == "Normal chat response."
    assert len(provider.calls) == 1
    assert provider.calls[0]["model"] == "fake-chat"


def test_unified_runtime_keeps_conversation_memory_isolated():
    provider = CountingProvider()
    runtime = UnifiedAgentRuntime(provider)
    history_a = [
        {"role": "user", "content": "My name is Alice."},
        {"role": "assistant", "content": "Nice to meet you."},
    ]
    history_b = [
        {"role": "user", "content": "My name is Bob."},
        {"role": "assistant", "content": "Nice to meet you."},
    ]

    runtime.execute(
        owner_id="owner-a",
        conversation_id="conversation-a",
        content="Hi",
        history=history_a,
        model="fake-chat",
    )
    runtime.execute(
        owner_id="owner-a",
        conversation_id="conversation-b",
        content="Hi",
        history=history_b,
        model="fake-chat",
    )

    messages_a = provider.calls[-2]["messages"]
    messages_b = provider.calls[-1]["messages"]
    assert {"role": "user", "content": "My name is Alice."} in messages_a
    assert {"role": "user", "content": "My name is Bob."} not in messages_a
    assert {"role": "user", "content": "My name is Bob."} in messages_b


def test_unified_runtime_executes_london_timezone_tool():
    provider = CountingProvider()
    runtime = UnifiedAgentRuntime(provider)

    result = runtime.execute(
        owner_id="owner-a",
        conversation_id="conversation-a",
        content="What time is it in London?",
        history=[],
    )

    assert "London" in result or "GMT" in result or "BST" in result
    assert provider.calls == []


def test_unified_runtime_preserves_equality_expression():
    provider = CountingProvider()
    runtime = UnifiedAgentRuntime(provider)

    result = runtime.execute(
        owner_id="owner-a",
        conversation_id="conversation-a",
        content="2=2",
        history=[],
    )

    assert result == "True"
    assert provider.calls == []


def test_calculator_supports_arithmetic_and_comparisons():
    tool = CalculatorTool()

    assert tool.execute(expression="2+2") == "4"
    assert tool.execute(expression="25*4") == "100"
    assert tool.execute(expression="10/2") == "5.0"
    assert tool.execute(expression="2=2") == "True"
    assert tool.execute(expression="2=3") == "False"
    assert tool.execute(expression="10>5") == "True"
    assert tool.execute(expression="5<2") == "False"
    assert tool.execute(expression="2+3*4") == "14"
    assert tool.execute(expression="(2+3)*4") == "20"


def test_calculator_rejects_unsafe_and_invalid_expressions():
    tool = CalculatorTool()

    assert "unsafe" in tool.execute(expression="__import__('os')").lower()
    assert "division by zero" in tool.execute(expression="1/0").lower()
    assert "calculation failed" in tool.execute(expression="2+").lower()


def test_unified_runtime_resolves_germany_timezone():
    provider = CountingProvider()
    runtime = UnifiedAgentRuntime(provider)

    result = runtime.execute(
        owner_id="owner-a",
        conversation_id="conversation-a",
        content="What time is it in Germany?",
        history=[],
    )

    assert "Germany" in result
    assert "GMT" not in result or "CET" in result or "CEST" in result
    assert provider.calls == []


def test_unified_runtime_asks_clarification_for_australia():
    provider = CountingProvider()
    runtime = UnifiedAgentRuntime(provider)

    result = runtime.execute(
        owner_id="owner-a",
        conversation_id="conversation-a",
        content="What time is it in Australia?",
        history=[],
    )

    assert "Australian city" in result
    assert provider.calls == []


def test_unified_runtime_executes_contextual_time_follow_up():
    provider = CountingProvider()
    runtime = UnifiedAgentRuntime(provider)
    history = [
        {"role": "user", "content": "What time is it in Germany?"},
        {"role": "assistant", "content": "Current time in Germany: CET"},
    ]

    result = runtime.execute(
        owner_id="owner-a",
        conversation_id="conversation-a",
        content="and India",
        history=history,
    )

    assert "India" in result
    assert provider.calls == []


def test_unified_runtime_explicit_tool_instruction_reuses_context():
    provider = CountingProvider()
    runtime = UnifiedAgentRuntime(provider)
    history = [
        {"role": "user", "content": "What time is it in India?"},
        {"role": "assistant", "content": "Current time in India: IST"},
    ]

    result = runtime.execute(
        owner_id="owner-a",
        conversation_id="conversation-a",
        content="use tool",
        history=history,
    )

    assert "India" in result
    assert provider.calls == []


def test_unified_runtime_does_not_reuse_time_context_for_unrelated_question():
    provider = CountingProvider()
    runtime = UnifiedAgentRuntime(provider)
    history = [
        {"role": "user", "content": "What time is it in Germany?"},
        {"role": "assistant", "content": "Current time in Germany: CET"},
    ]

    result = runtime.execute(
        owner_id="owner-a",
        conversation_id="conversation-a",
        content="What is the weather?",
        history=history,
    )

    assert result == "Normal chat response."
    assert len(provider.calls) == 1
