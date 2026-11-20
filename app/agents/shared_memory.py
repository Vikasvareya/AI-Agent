from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock


@dataclass
class SharedMessage:
    sender: str
    recipient: str
    content: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class SharedMemory:
    def __init__(self):
        self._values: dict[str, object] = {}
        self.messages: list[SharedMessage] = []
        self._lock = Lock()

    def set(self, key: str, value: object) -> None:
        with self._lock:
            self._values[key] = value

    def get(self, key: str, default=None):
        with self._lock:
            return self._values.get(key, default)

    def publish(self, sender: str, recipient: str, content: str) -> SharedMessage:
        message = SharedMessage(sender, recipient, content)
        with self._lock:
            self.messages.append(message)
        return message

    def clear(self) -> None:
        with self._lock:
            self._values.clear()
            self.messages.clear()
