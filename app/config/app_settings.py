from dataclasses import dataclass

from app.config.providers.ollama_settings import OllamaSettings


@dataclass(frozen=True)
class AppSettings:
    """
    Root application configuration.
    """

    provider: OllamaSettings