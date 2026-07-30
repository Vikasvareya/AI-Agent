from app.context.conversation_context import ConversationContext
from app.context.pronoun_resolver import PronounResolver

context = ConversationContext()
context.last_entity = "Python"

resolver = PronounResolver()

tests = [
    "Who created it?",
    "How old is he?",
    "Tell me about she.",
    "Where are they?",
    "Hello",
]

for text in tests:

    print(text)
    print(" ->", resolver.resolve(text, context))
    print()