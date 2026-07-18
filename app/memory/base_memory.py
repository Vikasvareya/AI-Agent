from abc import ABC, abstractmethod


class BaseMemory(ABC):
    """
    Abstract base class for conversation memory implementations.
    """

    @abstractmethod
    def load(
        self,
        limit: int | None = None,
    ) -> list[dict[str, str]]:
        """
        Return the conversation history.

        If a limit is provided, return only the
        most recent messages.
        """
        pass

    @abstractmethod
    def save(self, role: str, content: str) -> None:
        """
        Save a message to memory.
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """
        Remove all stored conversation history.
        """
        pass