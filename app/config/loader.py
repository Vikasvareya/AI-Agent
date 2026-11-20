import os

from app.config.app_settings import AppSettings
from app.config.providers.openai_compatible_settings import (
    OpenAICompatibleSettings,
)
from app.config.providers.ollama_settings import OllamaSettings
from dotenv import load_dotenv


class Loader:
    """
    Loads application configuration.
    """

    def load(self) -> AppSettings:
        load_dotenv()

        provider_name = os.getenv("AI_AGENT_PROVIDER", "ollama").strip().lower()
        if provider_name == "ollama":
            provider = OllamaSettings(
                host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
                model=os.getenv("OLLAMA_MODEL", "llama3.2"),
                timeout=int(os.getenv("OLLAMA_TIMEOUT", "60")),
            )
        elif provider_name == "openai_compatible":
            api_key = os.getenv("OPENAI_COMPATIBLE_API_KEY", "").strip()
            provider = OpenAICompatibleSettings(
                base_url=os.getenv(
                    "OPENAI_COMPATIBLE_BASE_URL",
                    "https://api.openai.com/v1",
                ).strip(),
                model=os.getenv("OPENAI_COMPATIBLE_MODEL", "gpt-4o-mini").strip(),
                timeout=int(os.getenv("OPENAI_COMPATIBLE_TIMEOUT", "60")),
                api_key=api_key or None,
            )
        else:
            raise ValueError(
                "AI_AGENT_PROVIDER must be 'ollama' or 'openai_compatible'."
            )

        return AppSettings(
            provider=provider,
        )