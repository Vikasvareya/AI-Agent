# Retrieval-Augmented Generation

The current `RAGPipeline` retrieves documents from `VectorMemory` and formats
the selected content into a context string. `VectorMemory` uses normalized
term-frequency vectors in process memory; it does not use a learned embedding
model and does not persist documents across process restarts.

The CLI chat handler uses this RAG path. The HTTP API's `ChatService` does not
currently invoke it. There is no integrated document ingestion service,
tenant-aware index, citation/provenance system, or retrieval benchmark.

Treat documents as untrusted context. API integration is future work and
should require provenance, access-control filtering, retention policy, and
prompt-injection evaluation. See
[Product Roadmap](./PRODUCT_ROADMAP.md).
