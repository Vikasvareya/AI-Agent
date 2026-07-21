from dataclasses import dataclass

from app.config.providers.base_provider_settings import BaseProviderSettings


@dataclass(frozen=True)
class OllamaSettings(BaseProviderSettings):
    """
    Configuration specific to the Ollama provider.
    """

    host: str