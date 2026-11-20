# Context System

The context layer resolves references using conversation context and
entity/pronoun handling. It is a lightweight framework component intended to
help resolve follow-up prompts; it does not provide unlimited history,
semantic retrieval, or guaranteed coreference resolution.

Context resolution is distinct from persisted API conversations, coding
session context, and RAG. API chat currently supplies a bounded recent
conversation window to its provider. Coding sessions supply a smaller,
bounded recent window as untrusted context.

See `app/context/` and the relevant tests under `tests/context/`.
