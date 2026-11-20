from dataclasses import dataclass

from app.config.providers.openai_compatible_settings import (
    OpenAICompatibleSettings,
)
from app.config.providers.ollama_settings import OllamaSettings


ProviderSettings = OllamaSettings | OpenAICompatibleSettings


@dataclass(frozen=True)
class AppSettings:
    """
    Root application configuration.
    """

    provider: ProviderSettings