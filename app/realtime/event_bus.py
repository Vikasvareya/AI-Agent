from collections import deque
from threading import Lock
from uuid import uuid4

from app.realtime.models import AgentActivityEvent, WorkflowEvent


class EventBus:
    """
    In-process publish-subscribe event stream with bounded subscriber buffers.

    WebSocket adapters can consume events while subscriptions remain isolated.
    """

    def __init__(
        self,
        buffer_size: int = 100,
    ):
        if buffer_size <= 0:
            raise ValueError("buffer_size must be greater than zero.")

        self.buffer_size = buffer_size
        self._subscribers: dict[str, deque[WorkflowEvent]] = {}
        self._all_subscribers: set[str] = set()
        self._lock = Lock()

    def subscribe(
        self,
        run_id: str | None = None,
    ) -> str:
        subscription_id = f"subscriber-{uuid4()}"
        with self._lock:
            self._subscribers[subscription_id] = deque(
                maxlen=self.buffer_size
            )
            self._subscriber_filters = getattr(
                self,
                "_subscriber_filters",
                {},
            )
            self._subscriber_filters[subscription_id] = run_id
            if run_id is None:
                self._all_subscribers.add(subscription_id)
        return subscription_id

    def unsubscribe(
        self,
        subscription_id: str,
    ) -> bool:
        with self._lock:
            filters = getattr(self, "_subscriber_filters", {})
            filters.pop(subscription_id, None)
            self._all_subscribers.discard(subscription_id)
            return self._subscribers.pop(
                subscription_id,
                None,
            ) is not None

    def publish(
        self,
        run_id: str,
        event_type: str,
        payload: dict,
    ) -> WorkflowEvent:
        event = WorkflowEvent(
            run_id=run_id,
            event_type=event_type,
            payload=payload,
        )
        with self._lock:
            filters = getattr(self, "_subscriber_filters", {})
            for subscription_id, filtered_run_id in filters.items():
                if filtered_run_id == run_id:
                    buffer = self._subscribers[subscription_id]
                    buffer.append(event)

            for subscription_id in self._all_subscribers:
                filtered_run_id = filters.get(subscription_id)
                if filtered_run_id is None:
                    buffer = self._subscribers.setdefault(
                        subscription_id,
                        deque(maxlen=self.buffer_size),
                    )
                    buffer.append(event)

        return event

    def publish_activity(
        self,
        event: AgentActivityEvent,
    ) -> WorkflowEvent:
        return self.publish(
            event.run_id,
            event.event_type,
            event.to_dict(),
        )

    def consume(
        self,
        subscription_id: str,
        limit: int = 100,
    ) -> list[WorkflowEvent]:
        if limit <= 0:
            return []

        with self._lock:
            buffer = self._subscribers.get(subscription_id)
            if buffer is None:
                return []

            count = min(limit, len(buffer))
            return [
                buffer.popleft()
                for _ in range(count)
            ]
