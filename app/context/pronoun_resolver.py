import re

from app.context.conversation_context import ConversationContext


class PronounResolver:
    """
    Resolves simple pronouns using the current conversation context.
    """

    PRONOUNS = (
        "it",
        "he",
        "she",
        "they",
    )

    def resolve(
        self,
        prompt: str,
        context: ConversationContext,
    ) -> str:
        """
        Replace known pronouns with the last remembered entity.
        """

        if not context.last_entity:
            return prompt

        resolved = prompt

        for pronoun in self.PRONOUNS:

            resolved = re.sub(
                rf"\b{pronoun}\b",
                context.last_entity,
                resolved,
                flags=re.IGNORECASE,
            )

        return resolved