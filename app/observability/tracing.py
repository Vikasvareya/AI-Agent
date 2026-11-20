from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from time import perf_counter
from uuid import uuid4


@dataclass
class TraceSpan:
    name: str
    trace_id: str
    span_id: str = field(default_factory=lambda: str(uuid4()))
    parent_span_id: str | None = None
    attributes: dict = field(default_factory=dict)
    start_time: float = field(default_factory=perf_counter)
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    end_time: float | None = None
    status: str = "unset"

    def end(
        self,
        status: str = "ok",
        attributes: dict | None = None,
    ) -> None:
        self.end_time = perf_counter()
        self.status = status
        if attributes:
            self.attributes.update(attributes)

    @property
    def duration_seconds(self) -> float:
        end_time = self.end_time or perf_counter()
        return end_time - self.start_time

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "attributes": dict(self.attributes),
            "started_at": self.started_at,
            "duration_seconds": self.duration_seconds,
            "status": self.status,
        }


class Tracing:
    """
    Lightweight trace collector with parent/child span support.
    """

    def __init__(self):
        self._spans: dict[str, TraceSpan] = {}
        self._lock = Lock()

    def start_span(
        self,
        name: str,
        *,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        attributes: dict | None = None,
    ) -> TraceSpan:
        span = TraceSpan(
            name=name,
            trace_id=trace_id or str(uuid4()),
            parent_span_id=parent_span_id,
            attributes=attributes or {},
        )
        with self._lock:
            self._spans[span.span_id] = span
        return span

    def end_span(
        self,
        span: TraceSpan,
        status: str = "ok",
        attributes: dict | None = None,
    ) -> None:
        span.end(status=status, attributes=attributes)

    def get_trace(
        self,
        trace_id: str,
    ) -> list[dict]:
        with self._lock:
            return [
                span.to_dict()
                for span in self._spans.values()
                if span.trace_id == trace_id
            ]

    def snapshot(self) -> list[dict]:
        with self._lock:
            return [
                span.to_dict()
                for span in self._spans.values()
            ]
