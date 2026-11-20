from app.config.app_settings import AppSettings
from app.config.providers.openai_compatible_settings import (
    OpenAICompatibleSettings,
)
from app.providers.ollama_provider import OllamaProvider
from app.providers.openai_compatible_provider import OpenAICompatibleProvider
from app.providers.base_provider import BaseProvider


class ProviderFactory:
    """
    Factory responsible for creating AI providers.
    """

    def __init__(self, settings: AppSettings):
        self.settings = settings

    def create(self) -> BaseProvider:
        """
        Create the configured provider.
        """

        provider_settings = self.settings.provider

        if isinstance(provider_settings, OpenAICompatibleSettings):
            return OpenAICompatibleProvider(provider_settings)
        return OllamaProvider(provider_settings)