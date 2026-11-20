import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


@dataclass
class MemoryRecord:
    content: str
    importance: float = 0.5
    metadata: dict = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )


class LongTermMemory:
    """
    Persistent local memory with importance ranking and expiration.
    """

    def __init__(
        self,
        storage_path: str | Path = "data/long_term_memory.json",
    ):
        self.storage_path = Path(storage_path)
        self.records: dict[str, MemoryRecord] = {}
        self._load()

    def remember(
        self,
        content: str,
        *,
        importance: float = 0.5,
        metadata: dict | None = None,
    ) -> MemoryRecord:
        if not content.strip():
            raise ValueError("Memory content cannot be empty.")

        record = MemoryRecord(
            content=content.strip(),
            importance=max(
                0.0,
                min(1.0, importance),
            ),
            metadata=metadata or {},
        )
        self.records[record.id] = record
        self._save()
        return record

    def search(
        self,
        query: str,
        limit: int = 5,
    ) -> list[tuple[MemoryRecord, float]]:
        if limit <= 0:
            return []

        query_tokens = set(
            re.findall(r"[a-z0-9]+", query.lower())
        )
        if not query_tokens:
            return []

        matches: list[tuple[MemoryRecord, float]] = []

        for record in self.records.values():
            content_tokens = set(
                re.findall(
                    r"[a-z0-9]+",
                    record.content.lower(),
                )
            )
            overlap = len(
                query_tokens & content_tokens
            )
            if overlap:
                score = (
                    overlap
                    / len(query_tokens)
                    + record.importance
                )
                matches.append(
                    (record, score)
                )

        matches.sort(
            key=lambda item: (
                item[1],
                item[0].created_at,
            ),
            reverse=True,
        )
        return matches[:limit]

    def forget(
        self,
        record_id: str,
    ) -> bool:
        removed = self.records.pop(
            record_id,
            None,
        ) is not None
        if removed:
            self._save()
        return removed

    def prune(
        self,
        *,
        max_importance: float = 0.0,
    ) -> int:
        record_ids = [
            record_id
            for record_id, record in self.records.items()
            if record.importance <= max_importance
        ]
        for record_id in record_ids:
            del self.records[record_id]

        if record_ids:
            self._save()
        return len(record_ids)

    def summarize(
        self,
        limit: int = 10,
    ) -> str:
        records = sorted(
            self.records.values(),
            key=lambda record: (
                record.importance,
                record.created_at,
            ),
            reverse=True,
        )[:limit]

        if not records:
            return ""

        return "\n".join(
            f"- {record.content}"
            for record in records
        )

    def clear(self) -> None:
        self.records.clear()
        self._save()

    def _load(self) -> None:
        if not self.storage_path.exists():
            return

        try:
            with self.storage_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                raw_records = json.load(file)
        except (json.JSONDecodeError, OSError):
            return

        for raw_record in raw_records:
            record = MemoryRecord(
                id=raw_record["id"],
                content=raw_record["content"],
                importance=raw_record.get(
                    "importance",
                    0.5,
                ),
                metadata=raw_record.get(
                    "metadata",
                    {},
                ),
                created_at=raw_record.get(
                    "created_at",
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            self.records[record.id] = record

    def _save(self) -> None:
        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        with self.storage_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                [
                    asdict(record)
                    for record in self.records.values()
                ],
                file,
                indent=2,
            )
