from abc import ABC, abstractmethod


class BaseContextResolver(ABC):
    """
    Base class for resolving conversational context.
    """

    @abstractmethod
    def resolve(
        self,
        prompt: str,
    ) -> str:
        """
        Resolve the user's prompt using conversation context.
        """
        pass