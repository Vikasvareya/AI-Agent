from app.context.base_context_resolver import BaseContextResolver
from app.context.conversation_context import ConversationContext
from app.context.entity_extractor import EntityExtractor
from app.context.pronoun_resolver import PronounResolver


class ContextResolver(BaseContextResolver):
    """
    Coordinates conversational context resolution.

    Responsibilities:
    - Resolve pronouns
    - Detect new entities
    - Update conversation state
    """

    def __init__(self):
        self.context = ConversationContext()

        self.entity_extractor = EntityExtractor()

        self.pronoun_resolver = PronounResolver()

    def resolve(
        self,
        prompt: str,
    ) -> str:
        """
        Resolve conversational context.
        """

        # Step 1
        resolved_prompt = self.pronoun_resolver.resolve(
            prompt,
            self.context,
        )

        if resolved_prompt != prompt:
            print(f"[Context] Resolved: {resolved_prompt}")

        # Step 2
        entity = self.entity_extractor.extract(
            resolved_prompt,
        )

        # Step 3
        if entity:

            self.context.last_entity = entity

            print(
                f"[Context] Remembered entity: {entity}"
            )

        return resolved_prompt