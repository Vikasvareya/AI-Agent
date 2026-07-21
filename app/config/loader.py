import os

from app.config.app_settings import AppSettings
from app.config.providers.ollama_settings import OllamaSettings
from dotenv import load_dotenv


class Loader:
    """
    Loads application configuration.
    """

    def load(self) -> AppSettings:
        load_dotenv()

        provider = OllamaSettings(
            host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            model=os.getenv("OLLAMA_MODEL", "llama3.2"),
            timeout=int(os.getenv("OLLAMA_TIMEOUT", "60")),
        )

        return AppSettings(
            provider=provider,
        )