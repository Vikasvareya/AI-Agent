import json
from pathlib import Path
import re
import urllib.error
import urllib.request

import pytest

from app.api.http_server import WorkflowHTTPServer
from app.api.workflow_service import WorkflowAPIService
from app.chat.service import ChatService
from app.chat.store import ChatStore
from app.realtime.event_bus import EventBus
from app.workflows.engine import WorkflowEngine


class FakeProvider:
    def __init__(self):
        self.refresh_requests = []

    @property
    def default_model(self):
        return "fake-chat"

    @property
    def provider_name(self):
        return "fake"

    def list_models(self, *, refresh=False):
        self.refresh_requests.append(refresh)
        return [
            {"id": "fake-chat", "name": "Fake Chat", "provider": "fake"},
            {"id": "fake-code", "name": "Fake Code", "provider": "fake"},
        ]

    def ask(self, messages, *, model=None, timeout=None):
        return f"Reply to: {messages[-1]['content']}"


class FakeWebSearch:
    available = True

    def search(self, query):
        return [{
            "title": f"Results for {query}",
            "url": "https://example.com/search-result",
            "description": "A relevant result snippet.",
        }]


def test_chat_frontend_serves_built_bundle():
    dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if not (dist / "index.html").is_file():
        pytest.skip("Run npm run build to create chat frontend assets.")

    bus = EventBus()
    server = WorkflowHTTPServer(
        WorkflowAPIService(WorkflowEngine(event_bus=bus)),
        bus,
        host="127.0.0.1",
        port=0,
    )
    server.start()
    base_url = f"http://127.0.0.1:{server._server.server_address[1]}"

    try:
        with urllib.request.urlopen(f"{base_url}/chat/", timeout=2) as response:
            html = response.read().decode()
            assert response.status == 200
            assert "<title>AI Agent Workspace</title>" in html
        with urllib.request.urlopen(f"{base_url}/coding/", timeout=2) as response:
            assert response.status == 200
            assert "<title>AI Agent Workspace</title>" in response.read().decode()
        with urllib.request.urlopen(
            f"{base_url}/coding/share/preview-token",
            timeout=2,
        ) as response:
            assert response.status == 200
            assert "<title>AI Agent Workspace</title>" in response.read().decode()

        assets = re.findall(r'(?:src|href)="([^"]+\.(?:js|css))"', html)
        assert len(assets) == 2
        for asset in assets:
            with urllib.request.urlopen(base_url + asset, timeout=2) as response:
                assert response.status == 200
                assert int(response.headers["Content-Length"]) > 0
    finally:
        server.stop()


def _request(url, *, method="GET", body=None, cookie=None, token=None):
    headers = {}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if cookie:
        headers["Cookie"] = cookie
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers=headers,
    )


def test_guest_chat_is_cookie_scoped_and_works_without_account(tmp_path):
    bus = EventBus()
    api = WorkflowAPIService(WorkflowEngine(event_bus=bus))
    provider = FakeProvider()
    server = WorkflowHTTPServer(
        api,
        bus,
        host="127.0.0.1",
        port=0,
        role_tokens={"user-token": "user"},
        require_auth=True,
        chat_service=ChatService(
            ChatStore(tmp_path / "chat.sqlite3"),
            provider,
            web_search_provider=FakeWebSearch(),
        ),
    )
    server.start()
    base_url = f"http://127.0.0.1:{server._server.server_address[1]}"

    try:
        guest_request = _request(
            f"{base_url}/v1/chat/guest-sessions",
            method="POST",
        )
        with urllib.request.urlopen(guest_request, timeout=2) as response:
            assert response.status == 201
            cookie = response.headers["Set-Cookie"].split(";", 1)[0]

        resume_guest = _request(
            f"{base_url}/v1/chat/guest-sessions",
            method="POST",
            cookie=cookie,
        )
        with urllib.request.urlopen(resume_guest, timeout=2) as response:
            assert response.status == 200
            assert response.headers.get("Set-Cookie") is None

        models_request = _request(
            f"{base_url}/v1/chat/models",
            cookie=cookie,
        )
        with urllib.request.urlopen(models_request, timeout=2) as response:
            catalog = json.loads(response.read())
        assert [model["id"] for model in catalog["models"]] == [
            "fake-chat",
            "fake-code",
        ]
        refreshed_models = _request(
            f"{base_url}/v1/chat/models?refresh=true",
            cookie=cookie,
        )
        with urllib.request.urlopen(refreshed_models, timeout=2) as response:
            assert response.status == 200
        assert provider.refresh_requests == [False, True]

        capabilities_request = _request(
            f"{base_url}/v1/chat/capabilities",
            cookie=cookie,
        )
        with urllib.request.urlopen(capabilities_request, timeout=2) as response:
            capabilities = json.loads(response.read())
        assert {
            mode["id"]: mode["available"]
            for mode in capabilities["modes"]
        } == {
            "chat": True,
            "coding": True,
            "image": False,
            "video": False,
            "web_search": True,
        }

        create = _request(
            f"{base_url}/v1/chat/conversations",
            method="POST",
            body={"title": "Guest conversation"},
            cookie=cookie,
        )
        with urllib.request.urlopen(create, timeout=2) as response:
            conversation = json.loads(response.read())

        send = _request(
            f"{base_url}/v1/chat/conversations/{conversation['id']}/messages",
            method="POST",
            body={
                "content": "Hello",
                "client_message_id": "guest-message-1",
                "model": "fake-code",
                "mode": "coding",
            },
            cookie=cookie,
        )
        with urllib.request.urlopen(send, timeout=2) as response:
            result = json.loads(response.read())
        assert result["assistant_message"]["content"] == "Reply to: Hello"
        assert result["model"] == "fake-code"
        assert result["mode"] == "coding"

        searched = _request(
            f"{base_url}/v1/chat/conversations/{conversation['id']}/messages",
            method="POST",
            body={
                "content": "Summarize the results.",
                "client_message_id": "guest-message-search",
                "web_search": True,
                "search_query": "relevant source",
            },
            cookie=cookie,
        )
        with urllib.request.urlopen(searched, timeout=2) as response:
            search_result = json.loads(response.read())
        assert search_result["sources"][0]["url"] == "https://example.com/search-result"
        assert search_result["sources"][0]["title"] == "Results for relevant source"
        assert "Sources:" in search_result["assistant_message"]["content"]

        without_cookie = _request(
            f"{base_url}/v1/chat/conversations/{conversation['id']}",
        )
        try:
            urllib.request.urlopen(without_cookie, timeout=2)
            assert False, "Guest conversations must require their session."
        except urllib.error.HTTPError as error:
            assert error.code == 401

        other_user = _request(
            f"{base_url}/v1/chat/conversations/{conversation['id']}",
            token="user-token",
        )
        try:
            urllib.request.urlopen(other_user, timeout=2)
            assert False, "Account conversations must be isolated from guests."
        except urllib.error.HTTPError as error:
            assert error.code == 404
    finally:
        server.stop()


def test_chat_account_identity_is_tenant_scoped_across_token_rotation(tmp_path):
    bus = EventBus()
    server = WorkflowHTTPServer(
        WorkflowAPIService(WorkflowEngine(event_bus=bus)),
        bus,
        host="127.0.0.1",
        port=0,
        role_tokens={
            "alice-token": ("user", "tenant-a:alice"),
            "alice-rotated-token": ("user", "tenant-a:alice"),
            "bob-token": ("user", "tenant-a:bob"),
        },
        require_auth=True,
        chat_service=ChatService(
            ChatStore(tmp_path / "chat.sqlite3"),
            FakeProvider(),
        ),
    )
    server.start()
    base_url = f"http://127.0.0.1:{server._server.server_address[1]}"

    try:
        create = _request(
            f"{base_url}/v1/chat/conversations",
            method="POST",
            body={"title": "Account chat"},
            token="alice-token",
        )
        with urllib.request.urlopen(create, timeout=2) as response:
            conversation = json.loads(response.read())

        rotated = _request(
            f"{base_url}/v1/chat/conversations/{conversation['id']}",
            token="alice-rotated-token",
        )
        with urllib.request.urlopen(rotated, timeout=2) as response:
            assert response.status == 200

        foreign = _request(
            f"{base_url}/v1/chat/conversations/{conversation['id']}",
            token="bob-token",
        )
        try:
            urllib.request.urlopen(foreign, timeout=2)
            assert False, "Conversation data must be isolated by account subject."
        except urllib.error.HTTPError as error:
            assert error.code == 404
    finally:
        server.stop()
