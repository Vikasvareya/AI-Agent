from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """
    Base contract for every AI provider.

    Every provider in our framework
    (Gemini, Ollama, OpenAI, Claude, etc.)
    must implement this interface.
    """

    @abstractmethod
    def ask(self, messages: list[dict[str, str]]) -> str:
        """
        Send messages to the model
        and return the generated response.
        """
        pass