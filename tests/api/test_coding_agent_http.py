import json
import urllib.error
import urllib.request

from app.agents.coding_agent import CodingAgent
from app.api.http_server import WorkflowHTTPServer
from app.api.workflow_service import WorkflowAPIService
from app.chat.service import ChatService
from app.chat.store import ChatStore
from app.realtime.event_bus import EventBus
from app.workflows.engine import WorkflowEngine


class FakeProvider:
    default_model = "fake-code"
    provider_name = "fake"

    def __init__(self):
        self.requests = []
        self.diff_path = "main.py"

    def list_models(self, *, refresh=False):
        return [{"id": "fake-code"}]

    def ask(self, messages, *, model=None, timeout=None):
        self.requests.append(messages)
        return (
            "Summary\n```diff\n"
            f"diff --git a/{self.diff_path} b/{self.diff_path}\n"
            f"--- a/{self.diff_path}\n"
            f"+++ b/{self.diff_path}\n"
            "@@ -1 +1 @@\n"
            "-print('hello')\n"
            "+print('Hello')\n"
            "```"
        )


def _request(url, *, method="GET", body=None, token=None):
    headers = {}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(
        url,
        data=data,
        method=method,
        headers=headers,
    )


def test_coding_agent_api_is_admin_only_and_returns_unapplied_proposals(
    tmp_path,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "main.py").write_text("print('hello')\n", encoding="utf-8")
    (workspace / ".env").write_text("SECRET=value", encoding="utf-8")
    bus = EventBus()
    server = WorkflowHTTPServer(
        WorkflowAPIService(WorkflowEngine(event_bus=bus)),
        bus,
        host="127.0.0.1",
        port=0,
        role_tokens={
            "admin-token": "admin",
            "user-token": "user",
        },
        require_auth=True,
        coding_agent=CodingAgent(FakeProvider(), workspace),
    )
    server.start()
    base_url = f"http://127.0.0.1:{server._server.server_address[1]}"

    try:
        for token, expected_status in ((None, 401), ("user-token", 403)):
            try:
                urllib.request.urlopen(
                    _request(
                        f"{base_url}/v1/coding/files",
                        token=token,
                    ),
                    timeout=2,
                )
                assert False, "Only administrators can inspect coding workspaces."
            except urllib.error.HTTPError as error:
                assert error.code == expected_status

        with urllib.request.urlopen(
            _request(
                f"{base_url}/v1/coding/status",
                token="admin-token",
            ),
            timeout=2,
        ) as response:
            assert json.loads(response.read())["available"] is True

        with urllib.request.urlopen(
            _request(
                f"{base_url}/v1/coding/files",
                token="admin-token",
            ),
            timeout=2,
        ) as response:
            assert json.loads(response.read()) == {
                "files": ["main.py"],
                "truncated": False,
            }

        with urllib.request.urlopen(
            _request(
                f"{base_url}/v1/coding/permissions",
                token="admin-token",
            ),
            timeout=2,
        ) as response:
            assert json.loads(response.read())["mode"] == "manual"

        with urllib.request.urlopen(
            _request(
                f"{base_url}/v1/coding/models",
                token="admin-token",
            ),
            timeout=2,
        ) as response:
            assert json.loads(response.read())["models"][0]["id"] == "fake-code"

        with urllib.request.urlopen(
            _request(
                f"{base_url}/v1/coding/proposals",
                method="POST",
                body={
                    "task": "Improve the greeting.",
                    "files": ["main.py"],
                    "model": "fake-code",
                },
                token="admin-token",
            ),
            timeout=2,
        ) as response:
            proposal = json.loads(response.read())
        assert proposal["proposal"].startswith("Summary\n```diff")
        assert proposal["files"] == ["main.py"]
        assert proposal["model"] == "fake-code"
        assert proposal["permission_mode"] == "manual"
        assert proposal["applied"] is False
        assert proposal["status"] == "pending"

        try:
            urllib.request.urlopen(
                _request(
                    f"{base_url}/v1/coding/proposals/{proposal['proposal_id']}/apply",
                    method="POST",
                    body={},
                    token="user-token",
                ),
                timeout=2,
            )
            assert False, "Only administrators can apply coding proposals."
        except urllib.error.HTTPError as error:
            assert error.code == 403

        with urllib.request.urlopen(
            _request(
                f"{base_url}/v1/coding/proposals/{proposal['proposal_id']}/apply",
                method="POST",
                body={},
                token="admin-token",
            ),
            timeout=2,
        ) as response:
            assert json.loads(response.read())["applied"] is True
        assert (workspace / "main.py").read_text(encoding="utf-8") == "print('Hello')\n"

        with urllib.request.urlopen(
            _request(
                f"{base_url}/v1/coding/integrations",
                token="admin-token",
            ),
            timeout=2,
        ) as response:
            integrations = json.loads(response.read())
            assert integrations["mcp"]["connected"] == []
            assert integrations["model_training"]["supported"] is False

        with urllib.request.urlopen(
            _request(
                f"{base_url}/v1/coding/permissions",
                method="POST",
                body={"mode": "auto", "confirm_auto_apply": True},
                token="admin-token",
            ),
            timeout=2,
        ) as response:
            assert json.loads(response.read())["mode"] == "auto"
    finally:
        server.stop()


def test_coding_proposal_api_recovers_owner_permission_and_audit(
    tmp_path,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source_file = workspace / "main.py"
    source_file.write_text("print('hello')\n", encoding="utf-8")
    database_path = tmp_path / "chat.sqlite3"
    role_tokens = {
        "admin-one": ("admin", "operator-one"),
        "admin-two": ("admin", "operator-two"),
    }

    first_store = ChatStore(database_path)
    first_bus = EventBus()
    first_agent = CodingAgent(
        FakeProvider(),
        workspace,
        persistence_store=first_store,
    )
    first_server = WorkflowHTTPServer(
        WorkflowAPIService(WorkflowEngine(event_bus=first_bus)),
        first_bus,
        host="127.0.0.1",
        port=0,
        role_tokens=role_tokens,
        coding_agent=first_agent,
    )
    first_server.start()
    first_url = f"http://127.0.0.1:{first_server._server.server_address[1]}"

    try:
        with urllib.request.urlopen(
            _request(
                f"{first_url}/v1/coding/proposals",
                method="POST",
                body={
                    "task": "Update the greeting.",
                    "files": ["main.py"],
                },
                token="admin-one",
            ),
            timeout=3,
        ) as response:
            proposal = json.loads(response.read())
        with urllib.request.urlopen(
            _request(
                f"{first_url}/v1/coding/permissions",
                method="POST",
                body={"mode": "auto", "confirm_auto_apply": True},
                token="admin-one",
            ),
            timeout=3,
        ) as response:
            assert json.loads(response.read())["mode"] == "auto"
    finally:
        first_server.stop()
        first_store.close()

    second_store = ChatStore(database_path)
    second_bus = EventBus()
    second_agent = CodingAgent(
        FakeProvider(),
        workspace,
        persistence_store=second_store,
    )
    second_server = WorkflowHTTPServer(
        WorkflowAPIService(WorkflowEngine(event_bus=second_bus)),
        second_bus,
        host="127.0.0.1",
        port=0,
        role_tokens=role_tokens,
        coding_agent=second_agent,
    )
    second_server.start()
    second_url = f"http://127.0.0.1:{second_server._server.server_address[1]}"

    try:
        with urllib.request.urlopen(
            _request(
                f"{second_url}/v1/coding/permissions",
                token="admin-one",
            ),
            timeout=3,
        ) as response:
            permissions = json.loads(response.read())
        assert permissions["mode"] == "auto"
        assert permissions["reset_on_restart"] is False

        with urllib.request.urlopen(
            _request(
                f"{second_url}/v1/coding/proposals",
                token="admin-one",
            ),
            timeout=3,
        ) as response:
            restored_proposals = json.loads(response.read())["proposals"]
        assert [item["proposal_id"] for item in restored_proposals] == [
            proposal["proposal_id"]
        ]
        assert restored_proposals[0]["proposal"] == proposal["proposal"]

        with urllib.request.urlopen(
            _request(
                f"{second_url}/v1/coding/proposals",
                token="admin-two",
            ),
            timeout=3,
        ) as response:
            assert json.loads(response.read())["proposals"] == []

        foreign_apply = _request(
            f"{second_url}/v1/coding/proposals/{proposal['proposal_id']}/apply",
            method="POST",
            token="admin-two",
        )
        try:
            urllib.request.urlopen(foreign_apply, timeout=3)
            assert False, "A different coding owner must not apply the proposal"
        except urllib.error.HTTPError as error:
            assert error.code == 404

        with urllib.request.urlopen(
            _request(
                f"{second_url}/v1/coding/proposals/{proposal['proposal_id']}/apply",
                method="POST",
                token="admin-one",
            ),
            timeout=3,
        ) as response:
            applied = json.loads(response.read())
        assert applied["status"] == "applied"
        assert source_file.read_text(encoding="utf-8") == "print('Hello')\n"
        audit = second_store.list_coding_audit()
        assert {item["action"] for item in audit} == {
            "proposal_created",
            "permission_mode_set",
            "proposal_apply_started",
            "proposal_applied",
        }
        assert all(
            item["actor_id"] == second_server._coding_owner(
                ("admin", "operator-one")
            )
            for item in audit
        )
        assert "admin-one" not in repr(audit)
    finally:
        second_server.stop()
        second_store.close()


def test_project_editor_sessions_context_and_sharing_api(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    provider = FakeProvider()
    provider.diff_path = "sample-app/main.py"
    store = ChatStore(tmp_path / "chat.sqlite3")
    bus = EventBus()
    server = WorkflowHTTPServer(
        WorkflowAPIService(WorkflowEngine(event_bus=bus)),
        bus,
        host="127.0.0.1",
        port=0,
        role_tokens={
            "admin-token": "admin",
            "user-token": "user",
        },
        require_auth=True,
        chat_service=ChatService(store, provider),
        coding_agent=CodingAgent(provider, workspace),
    )
    server.start()
    base_url = f"http://127.0.0.1:{server._server.server_address[1]}"

    def request_json(path, *, method="GET", body=None, token="admin-token"):
        with urllib.request.urlopen(
            _request(
                f"{base_url}{path}",
                method=method,
                body=body,
                token=token,
            ),
            timeout=3,
        ) as response:
            return response.status, json.loads(response.read())

    try:
        _, created_project = request_json(
            "/v1/coding/projects",
            method="POST",
            body={"name": "sample-app"},
        )
        assert created_project["id"] == "sample-app"
        _, created_file = request_json(
            "/v1/coding/file",
            method="POST",
            body={
                "path": "sample-app/main.py",
                "content": "print('hello')\n",
                "create": True,
            },
        )
        assert created_file["saved"] is True
        _, loaded_file = request_json(
            "/v1/coding/file?path=sample-app%2Fmain.py",
        )
        assert loaded_file["content"] == "print('hello')\n"

        _, session = request_json(
            "/v1/coding/sessions",
            method="POST",
            body={"project_id": "sample-app", "title": "New session"},
        )
        response_status, proposal = request_json(
            "/v1/coding/proposals",
            method="POST",
            body={
                "task": "Update the greeting.",
                "project_id": "sample-app",
                "session_id": session["id"],
                "files": ["sample-app/main.py"],
            },
        )
        assert response_status == 200
        assert proposal["status"] == "pending"
        _, restored = request_json(
            f"/v1/coding/sessions/{session['id']}",
        )
        assert restored["title"] == "Update the greeting."
        assert [message["role"] for message in restored["messages"]] == [
            "user",
            "assistant",
        ]

        request_json(
            "/v1/coding/proposals",
            method="POST",
            body={
                "task": "Keep improving this feature.",
                "project_id": "sample-app",
                "session_id": session["id"],
                "files": ["sample-app/main.py"],
            },
        )
        assert "Prior session context" in provider.requests[1][1]["content"]

        _, share = request_json(
            f"/v1/coding/sessions/{session['id']}/share",
            method="POST",
            body={},
        )
        _, shared = request_json(
            f"/v1/coding/shared/{share['token']}",
            token=None,
        )
        assert shared["id"] == session["id"]
        assert len(shared["messages"]) == 4
        request_json(
            f"/v1/coding/sessions/{session['id']}/shares",
            method="DELETE",
        )
        try:
            urllib.request.urlopen(
                _request(f"{base_url}/v1/coding/shared/{share['token']}"),
                timeout=3,
            )
            assert False, "Revoked session shares must not be readable."
        except urllib.error.HTTPError as error:
            assert error.code == 404

        _, files = request_json(
            "/v1/coding/files?project=sample-app",
        )
        assert files["files"] == ["sample-app/main.py"]
    finally:
        server.stop()
        store.close()
