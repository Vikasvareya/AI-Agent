from app.observability.metrics import MetricsCollector
from app.observability.tracing import Tracing
from app.workflows.engine import WorkflowEngine
from app.workflows.models import Workflow, WorkflowNode


def test_metrics_increment_observes_and_snapshots():
    metrics = MetricsCollector()

    metrics.increment("workflow_runs_started")
    metrics.increment("workflow_runs_started")
    metrics.observe("workflow_duration", 0.25)

    assert metrics.get("workflow_runs_started") == 2
    assert metrics.get("workflow_duration.count") == 1
    assert metrics.get("workflow_duration.sum") == 0.25
    assert metrics.get("workflow_duration.max") == 0.25
    assert "workflow_runs_started" in metrics.snapshot()


def test_tracing_records_parent_and_child_spans():
    tracing = Tracing()
    parent = tracing.start_span(
        "workflow",
        attributes={"workflow": "test"},
    )
    child = tracing.start_span(
        "node",
        trace_id=parent.trace_id,
        parent_span_id=parent.span_id,
    )
    tracing.end_span(child)
    tracing.end_span(parent)

    trace = tracing.get_trace(parent.trace_id)

    assert len(trace) == 2
    assert {span["name"] for span in trace} == {"workflow", "node"}
    assert all(span["status"] == "ok" for span in trace)


def test_workflow_engine_exports_metrics_and_trace():
    tracing = Tracing()
    metrics = MetricsCollector()
    engine = WorkflowEngine(
        tracing=tracing,
        metrics=metrics,
    )
    workflow = Workflow(
        name="observable",
        nodes=[
            WorkflowNode(
                name="step",
                action=lambda context, dependencies: "done",
            )
        ],
    )

    run = engine.start(workflow)
    trace = tracing.snapshot()

    assert run.status.value == "completed"
    assert metrics.get("workflow_runs_started") == 1
    assert metrics.get("workflow_runs_completed") == 1
    assert metrics.get("workflow_duration.count") == 1
    assert len(trace) == 1
    assert trace[0]["name"] == "workflow.run"
