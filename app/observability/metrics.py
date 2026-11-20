from threading import Lock


class MetricsCollector:
    """
    Thread-safe in-process counters and duration summaries.

    Exportable values make this suitable for Prometheus/OpenTelemetry adapters.
    """

    def __init__(self):
        self._values: dict[str, float] = {}
        self._labels: dict[str, dict[str, str]] = {}
        self._lock = Lock()

    def increment(
        self,
        name: str,
        value: float = 1.0,
        labels: dict[str, str] | None = None,
    ) -> float:
        key = self._metric_key(name, labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + value
            self._labels[key] = labels or {}
            return self._values[key]

    def observe(
        self,
        name: str,
        duration_seconds: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        count_key = self._metric_key(
            f"{name}.count",
            labels,
        )
        sum_key = self._metric_key(
            f"{name}.sum",
            labels,
        )
        max_key = self._metric_key(
            f"{name}.max",
            labels,
        )

        with self._lock:
            self._values[count_key] = self._values.get(count_key, 0.0) + 1
            self._values[sum_key] = (
                self._values.get(sum_key, 0.0)
                + duration_seconds
            )
            self._values[max_key] = max(
                self._values.get(max_key, 0.0),
                duration_seconds,
            )
            self._labels[count_key] = labels or {}
            self._labels[sum_key] = labels or {}
            self._labels[max_key] = labels or {}

    def get(
        self,
        name: str,
        labels: dict[str, str] | None = None,
    ) -> float:
        if labels is None:
            with self._lock:
                matching = [
                    value
                    for key, value in self._values.items()
                    if key == name or key.startswith(f"{name}|")
                ]
                if not matching:
                    return 0.0
                return sum(matching)

        key = self._metric_key(name, labels)
        with self._lock:
            return self._values.get(key, 0.0)

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            return dict(self._values)

    def _metric_key(
        self,
        name: str,
        labels: dict[str, str] | None,
    ) -> str:
        if not labels:
            return name
        label_text = ",".join(
            f"{key}={labels[key]}"
            for key in sorted(labels)
        )
        return f"{name}|{label_text}"
