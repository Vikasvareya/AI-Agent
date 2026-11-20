import json
import urllib.error
import urllib.request

from app.api.http_server import (
    APIRateLimiter,
    WorkflowHTTPServer,
)
from app.api.workflow_service import WorkflowAPIService
from app.chat.store import ChatStore
from app.realtime.event_bus import EventBus
from app.workflows.engine import WorkflowEngine
from app.workflows.models import Workflow, WorkflowNode


def _start_server(
    *,
    api_token: str | None = None,
    max_requests: int = 100,
):
    bus = EventBus()
    engine = WorkflowEngine(event_bus=bus)
    api = WorkflowAPIService(engine)
    workflow = Workflow(
        name="http",
        nodes=[
            WorkflowNode(
                name="step",
                action=lambda context, dependencies: "done",
            )
        ],
    )
    api.register_workflow(workflow)
    server = WorkflowHTTPServer(
        api,
        bus,
        host="127.0.0.1",
        port=0,
        api_token=api_token,
        rate_limiter=APIRateLimiter(
            max_requests=max_requests,
        ),
    )
    server.start()
    port = server._server.server_address[1]
    return server, port, api, workflow


def test_http_health_and_run_creation():
    server, port, _, workflow = _start_server()

    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/health",
            timeout=2,
        ) as response:
            assert json.loads(response.read())["status"] == "ok"

        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/workflows/{workflow.id}/runs",
            data=json.dumps({"context": {"tenant": "test"}}).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            run = json.loads(response.read())
            assert response.status == 201
            assert run["status"] == "completed"
    finally:
        server.stop()


def test_http_bearer_authentication():
    server, port, _, _ = _start_server(
        api_token="secret",
    )

    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/health",
        )
        try:
            urllib.request.urlopen(request, timeout=2)
            assert False, "Expected unauthorized response"
        except urllib.error.HTTPError as exc:
            assert exc.code == 401

        authorized = urllib.request.Request(
            f"http://127.0.0.1:{port}/health",
            headers={"Authorization": "Bearer secret"},
        )
        with urllib.request.urlopen(authorized, timeout=2) as response:
            assert response.status == 200
    finally:
        server.stop()


def test_http_rate_limiter_blocks_excess_requests():
    server, port, _, _ = _start_server(
        max_requests=1,
    )

    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/health",
            timeout=2,
        ):
            pass

        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/health",
                timeout=2,
            )
            assert False, "Expected rate-limited response"
        except urllib.error.HTTPError as exc:
            assert exc.code == 429
    finally:
        server.stop()


def test_http_roles_restrict_workflow_creation_and_cancellation():
    bus = EventBus()
    api = WorkflowAPIService(WorkflowEngine(event_bus=bus))
    server = WorkflowHTTPServer(
        api,
        bus,
        host="127.0.0.1",
        port=0,
        role_tokens={
            "user-token": "user",
            "admin-token": "admin",
        },
    )
    server.start()
    port = server._server.server_address[1]

    try:
        user_create = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/workflows",
            data=json.dumps(
                {
                    "name": "user-created",
                    "nodes": [{"name": "step", "value": "done"}],
                }
            ).encode(),
            method="POST",
            headers={
                "Authorization": "Bearer user-token",
                "Content-Type": "application/json",
            },
        )
        try:
            urllib.request.urlopen(user_create, timeout=2)
            assert False, "Users must not create workflows"
        except urllib.error.HTTPError as exc:
            assert exc.code == 403

        admin_create = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/workflows",
            data=json.dumps(
                {
                    "name": "admin-created",
                    "nodes": [
                        {
                            "name": "step",
                            "type": "context",
                            "key": "message",
                            "requires_approval": True,
                        }
                    ],
                }
            ).encode(),
            method="POST",
            headers={
                "Authorization": "Bearer admin-token",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(admin_create, timeout=2) as response:
            workflow = json.loads(response.read())
            assert response.status == 201
            assert workflow["name"] == "admin-created"

        run_request = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/workflows/{workflow['id']}/runs",
            data=json.dumps({"context": {"message": "result"}}).encode(),
            method="POST",
            headers={
                "Authorization": "Bearer user-token",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(run_request, timeout=2) as response:
            run = json.loads(response.read())
            assert run["status"] == "waiting_approval"

        user_cancel = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/runs/{run['id']}/cancel",
            data=b"{}",
            method="POST",
            headers={
                "Authorization": "Bearer user-token",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(user_cancel, timeout=2) as response:
            cancelled = json.loads(response.read())
            assert response.status == 200
            assert cancelled["status"] == "cancelled"
    finally:
        server.stop()


def test_http_user_only_sees_owned_runs():
    bus = EventBus()
    api = WorkflowAPIService(WorkflowEngine(event_bus=bus))
    workflow = Workflow(
        name="private-run",
        nodes=[
            WorkflowNode(
                name="approval",
                action=lambda context, dependencies: "done",
                requires_approval=True,
            )
        ],
    )
    api.register_workflow(workflow)
    server = WorkflowHTTPServer(
        api,
        bus,
        host="127.0.0.1",
        port=0,
        role_tokens={
            "user-one": "user",
            "user-two": "user",
        },
    )
    server.start()
    port = server._server.server_address[1]

    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/workflows/{workflow.id}/runs",
            data=b"{}",
            method="POST",
            headers={
                "Authorization": "Bearer user-one",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            run = json.loads(response.read())

        foreign_run = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/runs/{run['id']}",
            headers={"Authorization": "Bearer user-two"},
        )
        try:
            urllib.request.urlopen(foreign_run, timeout=2)
            assert False, "Users must not read another user's run"
        except urllib.error.HTTPError as exc:
            assert exc.code == 404

        foreign_cancel = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/runs/{run['id']}/cancel",
            data=b"{}",
            method="POST",
            headers={
                "Authorization": "Bearer user-two",
                "Content-Type": "application/json",
            },
        )
        try:
            urllib.request.urlopen(foreign_cancel, timeout=2)
            assert False, "Users must not cancel another user's run"
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
    finally:
        server.stop()


def test_http_approval_is_admin_only_and_audited_by_role():
    bus = EventBus()
    api = WorkflowAPIService(WorkflowEngine(event_bus=bus))
    workflow = Workflow(
        name="approval",
        nodes=[
            WorkflowNode(
                name="review",
                action=lambda context, dependencies: "approved",
                requires_approval=True,
            )
        ],
    )
    api.register_workflow(workflow)
    server = WorkflowHTTPServer(
        api,
        bus,
        host="127.0.0.1",
        port=0,
        role_tokens={
            "user-token": "user",
            "admin-token": "admin",
        },
    )
    server.start()
    port = server._server.server_address[1]

    try:
        start = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/workflows/{workflow.id}/runs",
            data=b"{}",
            method="POST",
            headers={
                "Authorization": "Bearer user-token",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(start, timeout=2) as response:
            run = json.loads(response.read())

        approval_url = (
            f"http://127.0.0.1:{port}/v1/runs/{run['id']}"
            "/approvals/review"
        )
        user_approval = urllib.request.Request(
            approval_url,
            data=json.dumps({"approved": True}).encode(),
            method="POST",
            headers={
                "Authorization": "Bearer user-token",
                "Content-Type": "application/json",
            },
        )
        try:
            urllib.request.urlopen(user_approval, timeout=2)
            assert False, "Users must not approve workflow steps"
        except urllib.error.HTTPError as exc:
            assert exc.code == 403

        admin_approval = urllib.request.Request(
            approval_url,
            data=json.dumps(
                {
                    "approved": True,
                    "approver": "spoofed-identity",
                }
            ).encode(),
            method="POST",
            headers={
                "Authorization": "Bearer admin-token",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(admin_approval, timeout=2) as response:
            approved = json.loads(response.read())

        assert approved["status"] == "completed"
        assert approved["approval_decisions"]["review"] == "admin"
    finally:
        server.stop()


def test_http_workflow_ownership_survives_restart_without_token_storage(
    tmp_path,
):
    database_path = tmp_path / "workflow-http.sqlite3"
    first_store = ChatStore(database_path)
    bus = EventBus()
    api = WorkflowAPIService(WorkflowEngine(event_bus=bus), first_store)
    workflow = api.create_workflow(
        {
            "name": "persistent http workflow",
            "nodes": [{"name": "step", "value": "done"}],
        }
    )
    role_tokens = {
        "user-token": ("user", "user-one"),
        "another-user-token": ("user", "user-two"),
    }
    first_server = WorkflowHTTPServer(
        api,
        bus,
        host="127.0.0.1",
        port=0,
        role_tokens=role_tokens,
    )
    first_server.start()
    port = first_server._server.server_address[1]

    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/workflows/{workflow['id']}/runs",
            data=b"{}",
            method="POST",
            headers={
                "Authorization": "Bearer user-token",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            run = json.loads(response.read())
    finally:
        first_server.stop()
        first_store.close()

    second_store = ChatStore(database_path)
    second_bus = EventBus()
    second_api = WorkflowAPIService(
        WorkflowEngine(event_bus=second_bus),
        second_store,
    )
    stored_run = second_store.list_workflow_runs()[0]
    second_server = WorkflowHTTPServer(
        second_api,
        second_bus,
        host="127.0.0.1",
        port=0,
        role_tokens=role_tokens,
    )
    second_server.start()
    second_port = second_server._server.server_address[1]

    try:
        assert stored_run["owner_id"] == second_server._workflow_owner(
            ("user", "user-one")
        )
        assert "user-token" not in repr(stored_run)
        own_runs = urllib.request.Request(
            f"http://127.0.0.1:{second_port}/v1/runs",
            headers={"Authorization": "Bearer user-token"},
        )
        with urllib.request.urlopen(own_runs, timeout=2) as response:
            runs = json.loads(response.read())["runs"]
        assert [item["id"] for item in runs] == [run["id"]]

        foreign_run = urllib.request.Request(
            f"http://127.0.0.1:{second_port}/v1/runs/{run['id']}",
            headers={"Authorization": "Bearer another-user-token"},
        )
        try:
            urllib.request.urlopen(foreign_run, timeout=2)
            assert False, "Users must not read another user's recovered run"
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
    finally:
        second_server.stop()
        second_store.close()


def test_sse_stream_includes_current_terminal_run_state():
    bus = EventBus()
    engine = WorkflowEngine(event_bus=bus)
    api = WorkflowAPIService(engine)
    workflow = Workflow(
        name="completed",
        nodes=[
            WorkflowNode(
                name="step",
                action=lambda context, dependencies: "done",
            )
        ],
    )
    api.register_workflow(workflow)
    run = engine.start(workflow)
    server = WorkflowHTTPServer(
        api,
        bus,
        host="127.0.0.1",
        port=0,
    )
    server.start()
    port = server._server.server_address[1]

    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/v1/runs/{run.id}/events",
            timeout=3,
        ) as response:
            stream = response.read().decode()
            assert response.headers.get("Content-Type") == "text/event-stream"
            assert "event: workflow.status" in stream
            assert '"status": "completed"' in stream
    finally:
        server.stop()
