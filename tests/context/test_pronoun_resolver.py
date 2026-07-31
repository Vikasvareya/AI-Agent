from app.context.conversation_context import ConversationContext
from app.context.pronoun_resolver import PronounResolver


def test_replace_it():
    context = ConversationContext()
    context.last_entity = "Python"

    resolver = PronounResolver()

    result = resolver.resolve(
        "Who created it?",
        context,
    )

    assert result == "Who created Python?"


def test_replace_he():
    context = ConversationContext()
    context.last_entity = "Elon Musk"

    resolver = PronounResolver()

    result = resolver.resolve(
        "Where does he work?",
        context,
    )

    assert result == "Where does Elon Musk work?"


def test_replace_she():
    context = ConversationContext()
    context.last_entity = "Taylor Swift"

    resolver = PronounResolver()

    result = resolver.resolve(
        "How old is she?",
        context,
    )

    assert result == "How old is Taylor Swift?"


def test_replace_they():
    context = ConversationContext()
    context.last_entity = "Developers"

    resolver = PronounResolver()

    result = resolver.resolve(
        "Where are they?",
        context,
    )

    assert result == "Where are Developers?"


def test_no_entity():
    context = ConversationContext()

    resolver = PronounResolver()

    result = resolver.resolve(
        "Who created it?",
        context,
    )

    assert result == "Who created it?"


def test_no_pronoun():
    context = ConversationContext()
    context.last_entity = "Python"

    resolver = PronounResolver()

    result = resolver.resolve(
        "Tell me about Laravel.",
        context,
    )

    assert result == "Tell me about Laravel."