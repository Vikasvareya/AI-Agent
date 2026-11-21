from app.context.context_resolver import ContextResolver


def test_remember_first_entity():
    resolver = ContextResolver()

    result = resolver.resolve("Tell me about Python.")

    assert result == "Tell me about Python."
    assert resolver.context.last_entity == "Python"


def test_pronoun_resolution():
    resolver = ContextResolver()

    resolver.resolve("Tell me about Python.")

    result = resolver.resolve("Who created it?")

    assert result == "Who created Python?"
    assert resolver.context.last_entity == "Python"


def test_context_updates_with_new_entity():
    resolver = ContextResolver()

    resolver.resolve("Tell me about Python.")

    resolver.resolve("Tell me about Laravel.")

    assert resolver.context.last_entity == "Laravel"


def test_pronoun_after_context_switch():
    resolver = ContextResolver()

    resolver.resolve("Tell me about Python.")

    resolver.resolve("Tell me about Laravel.")

    result = resolver.resolve("Who created it?")

    assert result == "Who created Laravel?"


def test_no_entity_prompt():
    resolver = ContextResolver()

    result = resolver.resolve("Hello")

    assert result == "Hello"
    assert resolver.context.last_entity is None


def test_time_context_follow_up_changes_location():
    resolver = ContextResolver()
    resolver.resolve("What time is it in Germany?")

    result = resolver.resolve("and India")

    assert result == "What time is it in India?"
    assert resolver.context.last_action == "current_time"
    assert resolver.context.last_location == "India"
    assert resolver.context.last_tool == "time"


def test_explicit_tool_uses_recent_time_context():
    resolver = ContextResolver()
    resolver.resolve("What time is it in Germany?")

    result = resolver.resolve("use tool")

    assert result == "What time is it in Germany?"
    assert resolver.context.last_action == "current_time"
    assert resolver.context.last_location == "Germany"


def test_use_tool_without_context_asks_for_task():
    resolver = ContextResolver()

    result = resolver.resolve("use tool")

    assert "specify" in result.lower()


def test_unrelated_question_clears_time_context():
    resolver = ContextResolver()
    resolver.resolve("What time is it in Germany?")

    result = resolver.resolve("What is the weather?")

    assert result == "What is the weather?"
    assert resolver.context.last_action is None
    assert resolver.context.last_location is None