from types import SimpleNamespace
from urllib.error import URLError

from app.config.providers.ollama_settings import OllamaSettings
from app.providers.ollama_provider import OllamaProvider


class FakeOllamaClient:
    def __init__(self):
        self.list_calls = 0
        self.chat_calls = []

    def list(self):
        self.list_calls += 1
        return SimpleNamespace(
            models=[
                SimpleNamespace(model="zeta:latest"),
                SimpleNamespace(model="alpha:latest"),
                SimpleNamespace(model=None),
            ]
        )

    def chat(self, *, model, messages):
        self.chat_calls.append((model, messages))
        return {"message": {"content": "response"}}


def test_ollama_catalog_cache_refresh_and_model_switch():
    provider = OllamaProvider(
        OllamaSettings(
            host="http://localhost:11434",
            model="alpha:latest",
            timeout=10,
        )
    )
    client = FakeOllamaClient()
    provider.client = client

    assert [model["id"] for model in provider.list_models()] == [
        "alpha:latest",
        "zeta:latest",
    ]
    provider.list_models()
    assert client.list_calls == 1

    provider.list_models(refresh=True)
    assert client.list_calls == 2
    assert provider.default_model == "alpha:latest"

    messages = [{"role": "user", "content": "hello"}]
    assert provider.ask(messages, model="zeta:latest") == "response"
    assert client.chat_calls == [("zeta:latest", messages)]


def test_ollama_ask_closes_a_client_with_coding_timeout(monkeypatch):
    provider = OllamaProvider(
        OllamaSettings(
            host="http://localhost:11434",
            model="alpha:latest",
            timeout=10,
        )
    )
    provider.client = FakeOllamaClient()
    clients = []

    class TimeoutClient(FakeOllamaClient):
        def __init__(self, *, host, timeout):
            super().__init__()
            self.host = host
            self.timeout = timeout
            self.closed = False
            clients.append(self)

        def close(self):
            self.closed = True

    monkeypatch.setattr("app.providers.ollama_provider.Client", TimeoutClient)

    response = provider.ask(
        [{"role": "user", "content": "Suggest a small code change."}],
        timeout=120,
    )

    assert response == "response"
    assert len(clients) == 1
    assert clients[0].host == "http://localhost:11434"
    assert clients[0].timeout == 120
    assert clients[0].closed is True


def test_ollama_health_check_reports_service_availability(monkeypatch):
    provider = OllamaProvider(
        OllamaSettings(
            host="http://localhost:11434/",
            model="alpha:latest",
            timeout=10,
        )
    )
    requested = []

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    def available(url, *, timeout):
        requested.append((url, timeout))
        return Response()

    monkeypatch.setattr("app.providers.ollama_provider.urlopen", available)
    assert provider.health_check() is True
    assert requested == [("http://localhost:11434/", 2.0)]

    def unavailable(*_args, **_kwargs):
        raise URLError("service unavailable")

    monkeypatch.setattr("app.providers.ollama_provider.urlopen", unavailable)
    assert provider.health_check() is False
