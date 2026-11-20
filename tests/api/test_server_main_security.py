import pytest

from app.api.http_server import WorkflowHTTPServer
from app.api.security_config import read_boolean_env, validate_api_auth
from app.api import server_main
from app.api.server_main import create_demo_api


@pytest.mark.parametrize(
    "host",
    ["localhost", "127.0.0.1", "::1"],
)
def test_loopback_api_can_use_local_development_auth(host):
    validate_api_auth(
        host,
        require_auth=False,
        has_configured_token=False,
    )


@pytest.mark.parametrize(
    "host",
    ["0.0.0.0", "::", "192.0.2.5", "api.example.test"],
)
def test_non_loopback_api_requires_auth(host):
    with pytest.raises(ValueError, match="AI_AGENT_REQUIRE_AUTH=true"):
        validate_api_auth(
            host,
            require_auth=False,
            has_configured_token=False,
        )


def test_required_auth_needs_at_least_one_token():
    with pytest.raises(ValueError, match="no API, admin, or user token"):
        validate_api_auth(
            "0.0.0.0",
            require_auth=True,
            has_configured_token=False,
        )


def test_required_auth_accepts_configured_token():
    validate_api_auth(
        "0.0.0.0",
        require_auth=True,
        has_configured_token=True,
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("true", True),
        ("YES", True),
        ("1", True),
        ("false", False),
        ("no", False),
        ("0", False),
    ],
)
def test_boolean_environment_parser(monkeypatch, raw, expected):
    monkeypatch.setenv("AI_AGENT_REQUIRE_AUTH", raw)

    assert read_boolean_env("AI_AGENT_REQUIRE_AUTH") is expected


def test_boolean_environment_parser_rejects_unknown_value(monkeypatch):
    monkeypatch.setenv("AI_AGENT_REQUIRE_AUTH", "sometimes")

    with pytest.raises(ValueError, match="must be set to true or false"):
        read_boolean_env("AI_AGENT_REQUIRE_AUTH")


def test_http_server_rejects_unprotected_non_loopback_bind():
    api, event_bus = create_demo_api()

    with pytest.raises(ValueError, match="AI_AGENT_REQUIRE_AUTH=true"):
        WorkflowHTTPServer(
            api,
            event_bus,
            host="0.0.0.0",
            port=0,
        )


def test_server_main_rejects_unprotected_bind_before_provider_startup(
    monkeypatch,
):
    monkeypatch.setattr(server_main, "create_demo_api", lambda: (None, None))
    monkeypatch.setattr(
        server_main.Loader,
        "load",
        lambda self: object(),
    )
    monkeypatch.setattr(
        server_main,
        "ProviderFactory",
        lambda _settings: pytest.fail("Provider startup must not be reached."),
    )
    for name in (
        "AI_AGENT_API_TOKEN",
        "AI_AGENT_ADMIN_TOKEN",
        "AI_AGENT_USER_TOKEN",
        "AI_AGENT_USER_TOKENS",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AI_AGENT_API_HOST", "0.0.0.0")
    monkeypatch.setenv("AI_AGENT_REQUIRE_AUTH", "false")

    with pytest.raises(ValueError, match="AI_AGENT_REQUIRE_AUTH=true"):
        server_main.main()
