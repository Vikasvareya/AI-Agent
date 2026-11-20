from app.memory.vector_memory import VectorDocument, VectorMemory


class RAGPipeline:
    """
    Retrieves relevant knowledge and formats it for model context.
    """

    def __init__(
        self,
        memory: VectorMemory,
    ):
        self.memory = memory

    def add_document(
        self,
        content: str,
        metadata: dict | None = None,
    ) -> VectorDocument:
        return self.memory.add(
            content,
            metadata,
        )

    def retrieve(
        self,
        query: str,
        limit: int = 3,
    ) -> list[VectorDocument]:
        return [
            document
            for document, _ in self.memory.search(
                query,
                limit,
            )
        ]

    def build_context(
        self,
        query: str,
        limit: int = 3,
    ) -> str:
        documents = self.retrieve(
            query,
            limit,
        )
        if not documents:
            return ""

        sections = [
            f"[{index}] {document.content}"
            for index, document in enumerate(
                documents,
                start=1,
            )
        ]
        return (
            "Use the following retrieved context to answer. "
            "Do not claim information outside this context if it is not provided.\n\n"
            + "\n\n".join(sections)
        )
