from app.config.app_settings import AppSettings
from app.providers.ollama_provider import OllamaProvider


class ProviderFactory:
    """
    Factory responsible for creating AI providers.
    """

    def __init__(self, settings: AppSettings):
        self.settings = settings

    def create(self):
        """
        Create the configured provider.
        """

        provider_settings = self.settings.provider

        return OllamaProvider(provider_settings)