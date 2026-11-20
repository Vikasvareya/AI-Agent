from app.memory.rag import RAGPipeline
from app.memory.vector_memory import VectorMemory


def test_vector_memory_searches_relevant_document():
    memory = VectorMemory()
    memory.add(
        "Python was created by Guido van Rossum.",
        {"source": "history"},
    )
    memory.add(
        "The Moon orbits the Earth.",
        {"source": "astronomy"},
    )

    matches = memory.search(
        "Who created Python?",
        limit=1,
    )

    assert len(matches) == 1
    document, score = matches[0]
    assert "Python" in document.content
    assert score > 0


def test_vector_memory_rejects_empty_content():
    memory = VectorMemory()

    try:
        memory.add("   ")
        assert False, "Expected empty content to raise"
    except ValueError as exc:
        assert "cannot be empty" in str(exc)


def test_rag_builds_context_from_retrieved_documents():
    rag = RAGPipeline(
        VectorMemory(),
    )
    rag.add_document(
        "Python was created by Guido van Rossum.",
    )

    context = rag.build_context(
        "Who created Python?",
    )

    assert "Guido van Rossum" in context
    assert "retrieved context" in context


def test_rag_returns_no_context_for_no_relevant_documents():
    rag = RAGPipeline(
        VectorMemory(),
    )

    assert rag.retrieve("unknown query") == []
    assert rag.build_context("unknown query") == ""
