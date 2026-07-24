from app.context.base_context_resolver import BaseContextResolver


class ContextResolver(BaseContextResolver):
    """
    Initial implementation.

    For now, it simply returns the original prompt.
    """

    def resolve(
        self,
        prompt: str,
    ) -> str:
        return prompt