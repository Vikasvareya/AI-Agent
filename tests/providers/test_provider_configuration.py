import pytest

from app.config.loader import Loader
from app.config.providers.ollama_settings import OllamaSettings
from app.config.providers.openai_compatible_settings import (
    OpenAICompatibleSettings,
)
from app.factories.provider_factory import ProviderFactory
from app.providers.ollama_provider import OllamaProvider
from app.providers.openai_compatible_provider import (
    OpenAICompatibleProvider,
)


def test_loader_defaults_to_ollama(monkeypatch):
    monkeypatch.delenv("AI_AGENT_PROVIDER", raising=False)
    monkeypatch.setattr("app.config.loader.load_dotenv", lambda: None)
    monkeypatch.setenv("OLLAMA_HOST", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2")
    monkeypatch.setenv("OLLAMA_TIMEOUT", "60")

    settings = Loader().load()

    assert isinstance(settings.provider, OllamaSettings)
    assert isinstance(ProviderFactory(settings).create(), OllamaProvider)


def test_loader_configures_openai_compatible_provider(monkeypatch):
    monkeypatch.setenv("AI_AGENT_PROVIDER", "openai_compatible")
    monkeypatch.setenv(
        "OPENAI_COMPATIBLE_BASE_URL",
        "https://provider.example.test/v1",
    )
    monkeypatch.setenv("OPENAI_COMPATIBLE_MODEL", "test-model")
    monkeypatch.setenv("OPENAI_COMPATIBLE_TIMEOUT", "35")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "test-key")

    settings = Loader().load()

    assert isinstance(settings.provider, OpenAICompatibleSettings)
    assert settings.provider.model == "test-model"
    assert settings.provider.timeout == 35
    assert settings.provider.api_key == "test-key"
    assert isinstance(
        ProviderFactory(settings).create(),
        OpenAICompatibleProvider,
    )


def test_loader_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("AI_AGENT_PROVIDER", "unknown")

    with pytest.raises(ValueError, match="AI_AGENT_PROVIDER"):
        Loader().load()
