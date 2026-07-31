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