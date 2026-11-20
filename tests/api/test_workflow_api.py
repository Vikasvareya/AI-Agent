import pytest

from app.api.workflow_service import APIError, WorkflowAPIService
from app.chat.store import ChatStore
from app.workflows.engine import WorkflowEngine
from app.workflows.models import Workflow, WorkflowNode


def test_api_registers_workflow_and_creates_run():
    engine = WorkflowEngine()
    api = WorkflowAPIService(engine)
    workflow = Workflow(
        name="api-workflow",
        nodes=[
            WorkflowNode(
                name="step",
                action=lambda context, dependencies: "done",
            )
        ],
    )

    registered = api.register_workflow(workflow)
    created = api.create_run(
        workflow.id,
        idempotency_key="request-1",
        context={"tenant": "test"},
    )

    assert registered["name"] == "api-workflow"
    assert created["status"] == "completed"
    assert created["results"]["step"] == "done"
    assert created["idempotency_key"] == "request-1"


def test_api_idempotency_returns_same_run():
    engine = WorkflowEngine()
    api = WorkflowAPIService(engine)
    workflow = Workflow(
        name="idempotent",
        nodes=[
            WorkflowNode(
                name="step",
                action=lambda context, dependencies: "done",
            )
        ],
    )
    api.register_workflow(workflow)

    first = api.create_run(
        workflow.id,
        idempotency_key="same-request",
    )
    second = api.create_run(
        workflow.id,
        idempotency_key="same-request",
    )

    assert first["id"] == second["id"]


def test_api_approval_gate():
    engine = WorkflowEngine()
    api = WorkflowAPIService(engine)
    workflow = Workflow(
        name="approval",
        nodes=[
            WorkflowNode(
                name="protected",
                action=lambda context, dependencies: "approved",
                requires_approval=True,
            )
        ],
    )
    api.register_workflow(workflow)
    waiting = api.create_run(workflow.id)

    approved = api.decide_approval(
        waiting["id"],
        "protected",
        approved=True,
        approver="api-reviewer",
    )

    assert approved["status"] == "completed"
    assert approved["results"]["protected"] == "approved"
    assert approved["approval_decisions"]["protected"] == "api-reviewer"


def test_api_returns_structured_not_found_error():
    api = WorkflowAPIService(
        WorkflowEngine(),
    )

    with pytest.raises(APIError) as exc_info:
        api.create_run("missing-workflow")

    assert exc_info.value.code == "WORKFLOW_NOT_FOUND"
    assert exc_info.value.status_code == 404


def test_api_cancelled_run_state():
    engine = WorkflowEngine()
    api = WorkflowAPIService(engine)
    workflow = Workflow(
        name="cancellable",
        nodes=[
            WorkflowNode(
                name="approval",
                action=lambda context, dependencies: "done",
                requires_approval=True,
            )
        ],
    )
    api.register_workflow(workflow)
    waiting = api.create_run(workflow.id)

    cancelled = api.cancel_run(waiting["id"])

    assert cancelled["status"] == "cancelled"


def test_persisted_workflow_resumes_approval_and_idempotency(tmp_path):
    database_path = tmp_path / "workflow.sqlite3"
    first_store = ChatStore(database_path)
    first_api = WorkflowAPIService(
        WorkflowEngine(),
        first_store,
    )
    workflow = first_api.create_workflow(
        {
            "name": "persistent approval",
            "nodes": [
                {
                    "name": "input",
                    "type": "context",
                    "key": "message",
                },
                {
                    "name": "review",
                    "type": "value",
                    "value": "approved",
                    "dependencies": ["input"],
                    "requires_approval": True,
                },
            ],
        }
    )
    waiting = first_api.create_run(
        workflow["id"],
        idempotency_key="request-1",
        context={"message": "preserved"},
        owner_id="owner-digest",
    )
    first_store.close()

    second_store = ChatStore(database_path)
    try:
        second_api = WorkflowAPIService(
            WorkflowEngine(),
            second_store,
        )

        assert workflow["id"] in {
            item["id"] for item in second_api.list_workflows()
        }
        assert second_api.list_runs(owner_id="other-owner") == []
        assert second_api.list_runs(owner_id="owner-digest")[0]["status"] == (
            "waiting_approval"
        )
        replayed = second_api.create_run(
            workflow["id"],
            idempotency_key="request-1",
            owner_id="owner-digest",
        )
        assert replayed["id"] == waiting["id"]
        assert replayed["status"] == "waiting_approval"

        approved = second_api.decide_approval(
            waiting["id"],
            "review",
            approved=True,
            approver="admin",
        )
        assert approved["status"] == "completed"
        assert approved["results"]["input"] == "preserved"
        assert approved["results"]["review"] == "approved"
    finally:
        second_store.close()


def test_api_creates_validated_workflow_definition():
    api = WorkflowAPIService(WorkflowEngine())

    workflow = api.create_workflow(
        {
            "name": "created-workflow",
            "nodes": [
                {
                    "name": "message",
                    "type": "context",
                    "key": "message",
                },
                {
                    "name": "review",
                    "type": "value",
                    "value": "reviewed",
                    "dependencies": ["message"],
                    "requires_approval": True,
                    "timeout_seconds": 10,
                },
            ],
        }
    )

    assert workflow["name"] == "created-workflow"
    assert len(workflow["nodes"]) == 2
    assert workflow["nodes"][1]["requires_approval"] is True
    assert api.list_workflows()[0]["id"] == workflow["id"]


def test_api_rejects_unsafe_or_invalid_workflow_definition():
    api = WorkflowAPIService(WorkflowEngine())

    with pytest.raises(APIError) as invalid_type:
        api.create_workflow(
            {
                "name": "invalid",
                "nodes": [
                    {
                        "name": "execute",
                        "type": "python",
                    }
                ],
            }
        )
    assert invalid_type.value.code == "INVALID_WORKFLOW"

    with pytest.raises(APIError, match="cycle"):
        api.create_workflow(
            {
                "name": "cycle",
                "nodes": [
                    {
                        "name": "a",
                        "dependencies": ["b"],
                    },
                    {
                        "name": "b",
                        "dependencies": ["a"],
                    },
                ],
            }
        )
