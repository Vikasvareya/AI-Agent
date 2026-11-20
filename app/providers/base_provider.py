from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """
    Base contract for every AI provider.

    Every provider in our framework
    (Gemini, Ollama, OpenAI, Claude, etc.)
    must implement this interface.
    """

    @abstractmethod
    def ask(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        timeout: int | None = None,
    ) -> str:
        """
        Send messages to the model
        and return the generated response.
        """
        pass

    @abstractmethod
    def list_models(
        self,
        *,
        refresh: bool = False,
    ) -> list[dict[str, str]]:
        """Return the models available through this provider."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider's stable identifier."""
        pass

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Return the configured default model identifier."""
        pass


class ProviderError(RuntimeError):
    pass