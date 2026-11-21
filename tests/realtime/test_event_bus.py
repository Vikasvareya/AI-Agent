from app.realtime.event_bus import EventBus
from app.realtime.models import AgentActivityEvent
from app.workflows.engine import WorkflowEngine
from app.workflows.models import Workflow, WorkflowNode


def test_event_bus_delivers_run_filtered_events():
    bus = EventBus()
    subscription = bus.subscribe(run_id="run-1")
    bus.publish(
        "run-1",
        "workflow.status",
        {"status": "running"},
    )
    bus.publish(
        "run-2",
        "workflow.status",
        {"status": "running"},
    )

    events = bus.consume(subscription)

    assert len(events) == 1
    assert events[0].run_id == "run-1"
    assert events[0].payload["status"] == "running"


def test_event_bus_delivers_global_events():
    bus = EventBus()
    subscription = bus.subscribe()
    bus.publish(
        "run-1",
        "workflow.status",
        {"status": "completed"},
    )

    events = bus.consume(subscription)

    assert len(events) == 1
    assert events[0].event_type == "workflow.status"


def test_event_bus_isolated_subscription_buffers():
    bus = EventBus()
    first = bus.subscribe()
    second = bus.subscribe()
    bus.publish(
        "run-1",
        "workflow.status",
        {"status": "running"},
    )

    assert len(bus.consume(first)) == 1
    assert len(bus.consume(second)) == 1
    assert bus.consume(first) == []


def test_workflow_engine_publishes_status_events():
    bus = EventBus()
    engine = WorkflowEngine(event_bus=bus)
    subscription = bus.subscribe()
    workflow = Workflow(
        name="events",
        nodes=[
            WorkflowNode(
                name="step",
                action=lambda context, dependencies: "done",
            )
        ],
    )

    run = engine.start(workflow)
    events = bus.consume(subscription)

    assert run.status.value == "completed"
    assert events
    assert events[-1].payload["status"] == "completed"


def test_activity_event_is_delivered_through_existing_bus():
    bus = EventBus()
    subscription = bus.subscribe(run_id="chat-run-1")
    event = AgentActivityEvent(
        run_id="chat-run-1",
        conversation_id="conversation-1",
        event_type="cognitive.perception.completed",
        status="completed",
        summary="Request understood.",
        sequence_number=1,
    )

    bus.publish_activity(event)
    events = bus.consume(subscription)

    assert len(events) == 1
    assert events[0].event_type == "cognitive.perception.completed"
    assert events[0].payload["conversation_id"] == "conversation-1"
    assert events[0].payload["summary"] == "Request understood."
