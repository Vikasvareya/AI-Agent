# Persistent User Memory

## Status

AI Brain has a structured, owner-scoped persistent profile memory foundation.
It is stored in `ChatStore` alongside chat records and remains separate from
conversation working memory and general knowledge.

## Memory model

Each record contains:

- stable ID and owner digest
- optional conversation provenance
- category and key
- value
- source
- confidence
- status
- created/updated timestamps
- optional expiration
- structured metadata

Supported status values are `confirmed`, `pending_confirmation`, `rejected`,
`expired`, and `deleted`. The authoritative database record is deleted for
profile removal; rejected/expired states are available for future lifecycle
controls.

## Capture behavior

Explicit statements such as "Remember that I am a software engineer." create
confirmed records. Casual statements create `pending_confirmation` suggestions
and ask whether they should be remembered.

Passwords, API keys, credentials, secrets, medical, religious, political,
sexual, and financial-sensitive patterns are not stored. Memory text is treated
as data and is never allowed to override system instructions.

## Retrieval

Confirmed records belonging to the current owner are ranked by overlap with the
current request and a short, relevant subset is attached to runtime prompts.
Complete profiles are not attached to every request.

## API

- `GET /v1/memory/profile`
- `GET /v1/memory/records`
- `POST /v1/memory/records`
- `GET /v1/memory/records/{id}`
- `PATCH /v1/memory/records/{id}`
- `DELETE /v1/memory/records/{id}`
- `POST /v1/memory/profile/clear`

All operations are owner-scoped. Guest sessions receive isolated owner hashes;
cross-owner reads and writes return not found or unauthorized responses.

## Limitations

- Automatic memory extraction is intentionally limited to explicit patterns.
- Profile corrections preserve previous values in `memory_history` and require
  confirmation for chat-proposed corrections.
- Resume drafts can be created, edited, approved, listed, deleted, and exported
  as text. PDF/DOCX export is not implemented.
- Resume generation is chat-based and uses only confirmed profile records;
  PDF/DOCX export is not implemented.
- Vector/knowledge graph memory is not implemented.
- Pending confirmation is not yet a dedicated conversational accept/decline
  command.
- Historical values are not yet versioned separately.
