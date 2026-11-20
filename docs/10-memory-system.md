# Memory System

Memory components currently have different storage and integration boundaries:

- **Conversation memory:** in-process history used by framework/CLI paths.
- **Chat persistence:** SQLite or PostgreSQL storage for API conversations and
  coding sessions.
- **Long-term memory:** local JSON records with importance metadata and
  lexical token-overlap search.
- **Vector memory:** in-memory normalized token-frequency vectors with cosine
  similarity; these are not learned embeddings or durable vector storage.
- **RAG:** retrieves vector-memory documents and formats a context string. It
  is connected to the CLI `ChatHandler`, not API `ChatService`.

No shared multi-tenant memory service, embedding pipeline, retention policy,
or retrieval evaluation suite is established. Treat stored/retrieved content
as untrusted and do not put secrets in memory. See
[Current Implementation](./CURRENT_IMPLEMENTATION.md) and
[Known Limitations](./KNOWN_LIMITATIONS.md).
