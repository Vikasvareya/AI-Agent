from app.config.settings import settings
from app.providers.ollama_provider import OllamaProvider


class ProviderFactory:
    """
    Creates the correct AI provider
    based on application configuration.
    """

    @staticmethod
    def create():
        provider = settings.AI_PROVIDER.lower()

        if provider == "ollama":
            return OllamaProvider()

        raise ValueError(
            f"Unsupported provider: {provider}"
        )