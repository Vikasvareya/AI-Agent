# Architecture Decisions and Observations

## Status of this log

No historical architecture decision record (ADR) history was found in the
repository during this audit. The items below are current implementation
observations and future proposals, not reconstructed historical decisions.
Dates, authors, and original rationales are intentionally not invented.

## Current implementation observations

### Loopback-first API binding

The HTTP server defaults to loopback. A non-loopback bind requires explicit
authentication and at least one configured token; invalid boolean
configuration fails rather than silently disabling auth. This is a startup
guard, not managed identity or a replacement for network/TLS controls.

### Provider seam with one configured provider

`BaseProvider` and a factory establish an extension boundary, while the
factory currently creates only the Ollama provider. The interface should not
be described as multi-provider support until additional adapters and
conformance tests exist.

### Shared chat/session/workflow store, process-local execution controls

SQLite/PostgreSQL store chat, coding-session, and REST-workflow records.
REST-created JSON workflow definitions and run snapshots survive restart;
approval-waiting runs resume, while interrupted pending/running runs fail
closed. Coding proposals and permission mode also persist, with hashed-owner
scoping and audit events. Workflow execution coordination, permission-update
synchronization across live replicas, event subscriptions, and rate limiting
remain process-local. Persistent records do not make the application
multi-instance safe.

### In-process workflow DAG engine

The workflow engine executes dependencies with bounded thread concurrency,
retry and timeout handling, cancellation, callbacks, and approval gates. The
REST workflow surface uses a restricted node schema and persists supported
definitions/run snapshots through `ChatStore`; Python callers can construct
callable nodes, which are not persisted. Execution remains in-process.

### Explicitly bounded coding workspace

The coding agent scopes file operations to a configured workspace and uses
bounded selected-file context and validated patch proposals. Manual review is
the default. API-created pending proposals and permission mode persist through
`ChatStore`; proposal owners and audit actors are stored as identity digests.
An interrupted apply is invalidated on restart. Shell execution and external
tool invocation are not enabled.

### Separate CLI RAG path

The RAG implementation is called from the CLI chat handler; it is not wired
into API `ChatService`. The vector-memory implementation uses token-frequency
vectors in memory rather than learned embeddings.

## Proposed decisions requiring review

These are not accepted decisions:

1. Define an explicit supported single-instance deployment profile before
   claiming multi-instance support.
2. Select durable job and event infrastructure only after recovery,
   throughput, and tenancy requirements are measured.
3. Adopt tenant-aware identity and resource ownership before adding more
   shared integrations.
4. Require provider conformance tests and explicit capability metadata before
   advertising provider portability.
5. Require isolation and revocation for plugins, MCP servers, skills, or code
   execution before exposing them to the coding agent.

When a decision is approved, add a dated ADR with context, alternatives,
security and operational impact, rollout/rollback plan, and acceptance tests.
