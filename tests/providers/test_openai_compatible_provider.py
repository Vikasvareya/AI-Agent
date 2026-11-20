import json
from urllib.error import HTTPError

import pytest

from app.config.providers.openai_compatible_settings import (
    OpenAICompatibleSettings,
)
from app.providers.base_provider import ProviderError
from app.providers.openai_compatible_provider import (
    OpenAICompatibleProvider,
)


class FakeResponse:
    def __init__(self, value):
        self.body = json.dumps(value).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return self.body


def make_provider(**overrides):
    settings = {
        "base_url": "https://api.example.test/v1",
        "model": "default-model",
        "timeout": 12,
        "api_key": "test-key",
    }
    settings.update(overrides)
    return OpenAICompatibleProvider(OpenAICompatibleSettings(**settings))


def test_openai_compatible_lists_and_caches_models(monkeypatch):
    provider = make_provider()
    requests = []

    def open_url(request, *, timeout):
        requests.append((request, timeout))
        return FakeResponse({
            "data": [{"id": "zeta"}, {"id": "alpha"}, {"name": "invalid"}],
        })

    monkeypatch.setattr(
        "app.providers.openai_compatible_provider.urlopen",
        open_url,
    )

    assert [item["id"] for item in provider.list_models()] == ["alpha", "zeta"]
    provider.list_models()
    assert len(requests) == 1
    assert requests[0][0].full_url == "https://api.example.test/v1/models"
    assert requests[0][0].get_header("Authorization") == "Bearer test-key"
    assert requests[0][1] == 12

    provider.list_models(refresh=True)
    assert len(requests) == 2


def test_openai_compatible_chat_sends_selected_model_and_messages(monkeypatch):
    provider = make_provider()
    requested = []

    def open_url(request, *, timeout):
        requested.append((request, timeout))
        return FakeResponse({
            "choices": [{"message": {"content": "response"}}],
        })

    monkeypatch.setattr(
        "app.providers.openai_compatible_provider.urlopen",
        open_url,
    )
    messages = [{"role": "user", "content": "hello"}]

    assert provider.ask(messages, model="selected-model", timeout=45) == "response"
    request, timeout = requested[0]
    assert request.full_url == (
        "https://api.example.test/v1/chat/completions"
    )
    assert request.get_method() == "POST"
    assert json.loads(request.data) == {
        "model": "selected-model",
        "messages": messages,
    }
    assert timeout == 45


def test_openai_compatible_http_failure_does_not_expose_response_body(monkeypatch):
    provider = make_provider(api_key="sensitive-test-key")

    def reject_request(request, *, timeout):
        raise HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            None,
            None,
        )

    monkeypatch.setattr(
        "app.providers.openai_compatible_provider.urlopen",
        reject_request,
    )
    with pytest.raises(ProviderError, match="HTTP 401") as error:
        provider.list_models()
    assert "sensitive-test-key" not in str(error.value)


def test_openai_compatible_rejects_non_tls_remote_api_key():
    with pytest.raises(ValueError, match="require HTTPS"):
        OpenAICompatibleSettings(
            base_url="http://provider.example.test/v1",
            model="model",
            timeout=10,
            api_key="secret",
        )


@pytest.mark.parametrize(
    "base_url",
    [
        "https://provider.example.test:invalid/v1",
        "https://provider.example.test:70000/v1",
    ],
)
def test_openai_compatible_rejects_invalid_port(base_url):
    with pytest.raises(ValueError, match="valid port"):
        OpenAICompatibleSettings(
            base_url=base_url,
            model="model",
            timeout=10,
        )


def test_openai_compatible_allows_api_key_for_loopback_http():
    settings = OpenAICompatibleSettings(
        base_url="http://127.0.0.1:8080/v1",
        model="model",
        timeout=10,
        api_key="local-test-key",
    )

    assert settings.api_key == "local-test-key"
