import pytest

from app.workflows.engine import WorkflowEngine
from app.workflows.models import (
    ApprovalStatus,
    NodeStatus,
    Workflow,
    WorkflowNode,
    WorkflowRun,
    WorkflowStatus,
)


def test_workflow_executes_parallel_dependencies():
    workflow = Workflow(name="data-pipeline")
    workflow.add_node(
        WorkflowNode(
            name="first",
            action=lambda context, dependencies: "A",
        )
    )
    workflow.add_node(
        WorkflowNode(
            name="second",
            action=lambda context, dependencies: "B",
        )
    )
    workflow.add_node(
        WorkflowNode(
            name="join",
            dependencies=["first", "second"],
            action=lambda context, dependencies:
                dependencies["first"] + dependencies["second"],
        )
    )

    run = WorkflowEngine(max_workers=4).start(workflow)

    assert run.status is WorkflowStatus.COMPLETED
    assert run.results["join"] == "AB"
    assert run.node_statuses["join"] is NodeStatus.COMPLETED


def test_workflow_retries_node():
    calls = {"count": 0}

    def flaky(context, dependencies):
        calls["count"] += 1
        if calls["count"] < 3:
            raise RuntimeError("temporary")
        return "success"

    workflow = Workflow(
        name="retry",
        nodes=[
            WorkflowNode(
                name="flaky",
                action=flaky,
                retries=2,
            )
        ],
    )

    run = WorkflowEngine().start(workflow)

    assert run.status is WorkflowStatus.COMPLETED
    assert run.results["flaky"] == "success"
    assert calls["count"] == 3


def test_workflow_reports_failed_node():
    workflow = Workflow(
        name="failure",
        nodes=[
            WorkflowNode(
                name="broken",
                action=lambda context, dependencies: (_ for _ in ()).throw(
                    RuntimeError("broken")
                ),
            )
        ],
    )

    run = WorkflowEngine().start(workflow)

    assert run.status is WorkflowStatus.FAILED
    assert run.node_statuses["broken"] is NodeStatus.FAILED
    assert "broken" in run.errors


def test_workflow_rejects_cycle():
    workflow = Workflow(
        name="cycle",
        nodes=[
            WorkflowNode(
                name="a",
                dependencies=["b"],
                action=lambda context, dependencies: None,
            ),
            WorkflowNode(
                name="b",
                dependencies=["a"],
                action=lambda context, dependencies: None,
            ),
        ],
    )

    with pytest.raises(ValueError, match="cycle"):
        WorkflowEngine().start(workflow)


def test_workflow_idempotency_returns_existing_run():
    workflow = Workflow(
        name="idempotent",
        nodes=[
            WorkflowNode(
                name="step",
                action=lambda context, dependencies: "done",
            )
        ],
    )
    engine = WorkflowEngine()

    first = engine.start(
        workflow,
        idempotency_key="request-123",
    )
    second = engine.start(
        workflow,
        idempotency_key="request-123",
    )

    assert first is second


def test_workflow_checkpoint_callback_receives_runs():
    checkpoints = []
    workflow = Workflow(
        name="checkpoint",
        nodes=[
            WorkflowNode(
                name="step",
                action=lambda context, dependencies: "saved",
            )
        ],
    )

    run = WorkflowEngine(
        checkpoint_callback=checkpoints.append,
    ).start(workflow)

    assert len(checkpoints) >= 2
    assert checkpoints[-1] is run


def test_workflow_pauses_for_approval_and_resumes():
    workflow = Workflow(
        name="approval",
        nodes=[
            WorkflowNode(
                name="protected-action",
                action=lambda context, dependencies: "executed",
                requires_approval=True,
            )
        ],
    )
    engine = WorkflowEngine()

    waiting = engine.start(workflow)

    assert waiting.status is WorkflowStatus.WAITING_APPROVAL
    assert waiting.approvals["protected-action"] is ApprovalStatus.PENDING
    assert waiting.node_statuses["protected-action"] is NodeStatus.WAITING_APPROVAL

    approved = engine.approve(
        waiting.id,
        "protected-action",
        approved=True,
        approver="human-admin",
    )

    assert approved.status is WorkflowStatus.COMPLETED
    assert approved.results["protected-action"] == "executed"
    assert approved.approvals["protected-action"] is ApprovalStatus.APPROVED
    assert approved.approval_decisions["protected-action"] == "human-admin"


def test_workflow_rejection_fails_run():
    workflow = Workflow(
        name="rejected",
        nodes=[
            WorkflowNode(
                name="protected-action",
                action=lambda context, dependencies: "should-not-run",
                requires_approval=True,
            )
        ],
    )
    engine = WorkflowEngine()
    waiting = engine.start(workflow)

    rejected = engine.approve(
        waiting.id,
        "protected-action",
        approved=False,
        approver="reviewer",
    )

    assert rejected.status is WorkflowStatus.FAILED
    assert "protected-action" not in rejected.results
    assert rejected.approvals["protected-action"] is ApprovalStatus.REJECTED
    assert "rejected by 'reviewer'" in rejected.errors["protected-action"]


def test_restoring_interrupted_run_marks_it_failed_without_replaying():
    calls = []
    workflow = Workflow(
        name="interrupted",
        nodes=[
            WorkflowNode(
                name="side-effect",
                action=lambda context, dependencies: calls.append("ran"),
            )
        ],
    )
    run = WorkflowRun(
        workflow_id=workflow.id,
        status=WorkflowStatus.RUNNING,
        node_statuses={"side-effect": NodeStatus.RUNNING},
    )

    restored = WorkflowEngine().restore_run(workflow, run)

    assert restored.status is WorkflowStatus.FAILED
    assert restored.node_statuses["side-effect"] is NodeStatus.FAILED
    assert calls == []
