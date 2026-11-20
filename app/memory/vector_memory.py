import math
import re
from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class VectorDocument:
    content: str
    metadata: dict = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    embedding: dict[str, float] = field(default_factory=dict)


class VectorMemory:
    """
    Lightweight in-memory vector store using hashed term frequencies.

    The implementation has no external dependencies and is suitable for
    small knowledge bases and local learning experiments.
    """

    def __init__(self):
        self.documents: dict[str, VectorDocument] = {}

    def _embed(self, text: str) -> dict[str, float]:
        tokens = re.findall(
            r"[a-z0-9]+",
            text.lower(),
        )
        frequencies: dict[str, float] = {}

        for token in tokens:
            frequencies[token] = frequencies.get(token, 0.0) + 1.0

        if not frequencies:
            return {}

        norm = math.sqrt(
            sum(
                frequency * frequency
                for frequency in frequencies.values()
            )
        )
        return {
            token: frequency / norm
            for token, frequency in frequencies.items()
        }

    def add(
        self,
        content: str,
        metadata: dict | None = None,
    ) -> VectorDocument:
        if not content.strip():
            raise ValueError("Vector memory content cannot be empty.")

        document = VectorDocument(
            content=content,
            metadata=metadata or {},
            embedding=self._embed(content),
        )
        self.documents[document.id] = document
        return document

    def search(
        self,
        query: str,
        limit: int = 3,
    ) -> list[tuple[VectorDocument, float]]:
        if limit <= 0:
            return []

        query_embedding = self._embed(query)
        if not query_embedding:
            return []

        matches: list[tuple[VectorDocument, float]] = []

        for document in self.documents.values():
            shared_terms = (
                set(query_embedding)
                & set(document.embedding)
            )
            score = sum(
                query_embedding[token]
                * document.embedding[token]
                for token in shared_terms
            )
            if score > 0:
                matches.append(
                    (document, score)
                )

        matches.sort(
            key=lambda match: match[1],
            reverse=True,
        )
        return matches[:limit]

    def delete(
        self,
        document_id: str,
    ) -> bool:
        return self.documents.pop(
            document_id,
            None,
        ) is not None

    def clear(self) -> None:
        self.documents.clear()
