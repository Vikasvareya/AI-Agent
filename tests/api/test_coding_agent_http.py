import json
import urllib.error
import urllib.request
from urllib.parse import quote

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

        try:
            urllib.request.urlopen(
                _request(
                    f"{base_url}/v1/coding/projects/import",
                    method="POST",
                    body={"path": str(workspace)},
                    token="user-token",
                ),
                timeout=2,
            )
            assert False, "Only administrators can add coding projects."
        except urllib.error.HTTPError as error:
            assert error.code == 403
        try:
            urllib.request.urlopen(
                _request(
                    f"{base_url}/v1/coding/directories",
                    token="user-token",
                ),
                timeout=2,
            )
            assert False, "Only administrators can browse project locations."
        except urllib.error.HTTPError as error:
            assert error.code == 403

        for path in (
            "/v1/coding/projects/sample-app",
            "/v1/coding/sessions/session-id",
        ):
            try:
                urllib.request.urlopen(
                    _request(
                        f"{base_url}{path}",
                        method="DELETE",
                        token="user-token",
                    ),
                    timeout=2,
                )
                assert False, "Only administrators can delete coding data."
            except urllib.error.HTTPError as error:
                assert error.code == 403

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
        "user-token": "user",
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
        chat_service=ChatService(second_store, FakeProvider()),
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

        for token, expected_status in (
            (None, 401),
            ("user-token", 403),
        ):
            try:
                urllib.request.urlopen(
                    _request(
                        f"{second_url}/v1/coding/audit",
                        token=token,
                    ),
                    timeout=3,
                )
                assert False, "Coding audit must be restricted to administrators."
            except urllib.error.HTTPError as error:
                assert error.code == expected_status

        with urllib.request.urlopen(
            _request(
                f"{second_url}/v1/coding/audit?limit=2&offset=0",
                token="admin-one",
            ),
            timeout=3,
        ) as response:
            first_page = json.loads(response.read())
        assert first_page["limit"] == 2
        assert first_page["offset"] == 0
        assert first_page["has_more"] is True
        assert len(first_page["events"]) == 2

        with urllib.request.urlopen(
            _request(
                f"{second_url}/v1/coding/audit?limit=2&offset=2",
                token="admin-one",
            ),
            timeout=3,
        ) as response:
            second_page = json.loads(response.read())
        assert second_page["has_more"] is False
        assert len(second_page["events"]) == 2
        audit_page = first_page["events"] + second_page["events"]
        assert {item["action"] for item in audit_page} == {
            "proposal_created",
            "permission_mode_set",
            "proposal_apply_started",
            "proposal_applied",
        }
        assert all(
            len(item["actor_id"]) == 64
            and all(
                character in "0123456789abcdef"
                for character in item["actor_id"]
            )
            for item in audit_page
        )
        assert "admin-one" not in repr(audit_page)

        for query in (
            "limit=0",
            "limit=101",
            "limit=invalid",
            "limit=1&limit=2",
            "offset=10001",
        ):
            try:
                urllib.request.urlopen(
                    _request(
                        f"{second_url}/v1/coding/audit?{query}",
                        token="admin-one",
                    ),
                    timeout=3,
                )
                assert False, f"Expected invalid audit query: {query}"
            except urllib.error.HTTPError as error:
                assert error.code == 400

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

        with urllib.request.urlopen(
            _request(
                f"{second_url}/v1/audit?limit=100&offset=0",
                token="admin-one",
            ),
            timeout=3,
        ) as response:
            general_audit = json.loads(response.read())
        general_actions = {
            item["action"]
            for item in general_audit["events"]
        }
        assert "permission_mode_set" in general_actions
        assert "proposal_created" in general_actions
        assert "proposal_applied" in general_actions
        assert all(
            len(item["actor_id"]) == 64
            for item in general_audit["events"]
        )
        assert "admin-one" not in repr(general_audit)
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
        coding_agent=CodingAgent(
            provider,
            workspace,
            persistence_store=store,
        ),
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

        _, active_share = request_json(
            f"/v1/coding/sessions/{session['id']}/share",
            method="POST",
            body={},
        )
        _, deleted_session = request_json(
            f"/v1/coding/sessions/{session['id']}",
            method="DELETE",
        )
        assert deleted_session == {
            "id": session["id"],
            "deleted": True,
        }
        assert store.list_coding_proposals() == []
        for path, token in (
            (f"/v1/coding/sessions/{session['id']}", "admin-token"),
            (f"/v1/coding/shared/{active_share['token']}", None),
        ):
            try:
                urllib.request.urlopen(
                    _request(f"{base_url}{path}", token=token),
                    timeout=3,
                )
                assert False, "Deleted coding conversations must not be readable."
            except urllib.error.HTTPError as error:
                assert error.code == 404

        _, project_session = request_json(
            "/v1/coding/sessions",
            method="POST",
            body={"project_id": "sample-app", "title": "Project cleanup"},
        )
        _, project_share = request_json(
            f"/v1/coding/sessions/{project_session['id']}/share",
            method="POST",
            body={},
        )
        try:
            request_json(
                "/v1/coding/projects/%2E",
                method="DELETE",
            )
            assert False, "The workspace root must not be deletable."
        except urllib.error.HTTPError as error:
            assert error.code == 400

        _, deleted_project = request_json(
            "/v1/coding/projects/sample-app",
            method="DELETE",
        )
        assert deleted_project == {
            "id": "sample-app",
            "deleted": True,
            "files_deleted": True,
            "deleted_conversations": 1,
        }
        assert not (workspace / "sample-app").exists()
        for path, token in (
            (f"/v1/coding/sessions/{project_session['id']}", "admin-token"),
            (f"/v1/coding/shared/{project_share['token']}", None),
        ):
            try:
                urllib.request.urlopen(
                    _request(f"{base_url}{path}", token=token),
                    timeout=3,
                )
                assert False, "Deleting a project must remove its conversations."
            except urllib.error.HTTPError as error:
                assert error.code == 404

        external_parent = tmp_path / "other-location"
        external_parent.mkdir()
        existing_project_path = external_parent / "existing-app"
        existing_project_path.mkdir()
        existing_source = existing_project_path / "main.py"
        existing_source.write_bytes(b"print('hello')\n")
        _, directory_listing = request_json(
            f"/v1/coding/directories?path={quote(str(external_parent), safe='')}",
        )
        assert directory_listing["current"] == str(external_parent)
        assert [directory["name"] for directory in directory_listing["directories"]] == [
            "existing-app",
        ]
        _, existing_project = request_json(
            "/v1/coding/projects/import",
            method="POST",
            body={"path": str(existing_project_path)},
        )
        assert existing_project["external"] is True
        restarted_agent = CodingAgent(
            provider,
            workspace,
            persistence_store=store,
        )
        assert existing_project["id"] in {
            project["id"]
            for project in restarted_agent.list_projects()["projects"]
        }
        _, same_project = request_json(
            "/v1/coding/projects/import",
            method="POST",
            body={"path": str(existing_project_path)},
        )
        assert same_project["id"] == existing_project["id"]
        _, external_files = request_json(
            f"/v1/coding/files?project={existing_project['id']}",
        )
        assert external_files["files"] == [
            f"{existing_project['id']}/main.py",
        ]
        _, external_file = request_json(
            "/v1/coding/file?path="
            + quote(f"{existing_project['id']}/main.py", safe=""),
        )
        assert external_file["content"] == "print('hello')\n"
        provider.diff_path = f"{existing_project['id']}/main.py"
        _, external_proposal = request_json(
            "/v1/coding/proposals",
            method="POST",
            body={
                "task": "Update the external project greeting.",
                "project_id": existing_project["id"],
                "files": [f"{existing_project['id']}/main.py"],
            },
        )
        _, applied_external_proposal = request_json(
            f"/v1/coding/proposals/{external_proposal['proposal_id']}/apply",
            method="POST",
            body={},
        )
        assert applied_external_proposal["applied"] is True
        assert existing_source.read_text(encoding="utf-8") == "print('Hello')\n"

        _, created_external_project = request_json(
            "/v1/coding/projects",
            method="POST",
            body={
                "name": "new-location-app",
                "parent_path": str(external_parent),
            },
        )
        created_external_path = external_parent / "new-location-app"
        assert created_external_project["external"] is True
        assert created_external_path.is_dir()
        _, removed_external_project = request_json(
            f"/v1/coding/projects/{created_external_project['id']}",
            method="DELETE",
        )
        assert removed_external_project["files_deleted"] is False
        assert created_external_path.is_dir()
    finally:
        server.stop()
        store.close()
