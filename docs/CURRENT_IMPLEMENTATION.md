# Current Implementation

This document describes repository behavior observed in source and tests. It
does not describe the target architecture. See [Known Limitations](./KNOWN_LIMITATIONS.md)
for constraints that affect deployment and use.

## Runtime entry points

- `python -m app.api.server_main` starts the API on port `8081` by default and
  the health server on port `8080`. Environment variables can change hosts and
  ports.
- `python main.py` starts the older interactive CLI. It is not the API server.
- The frontend is a Vite/React application built from `frontend/`; the API
  serves it under `/chat/`, with the coding workspace under `/coding/`.

## Capability inventory

| Area | Verified implementation | Important boundary |
| --- | --- | --- |
| Providers | `BaseProvider`, Ollama, and an OpenAI-compatible Chat Completions adapter | Select one provider per server with `AI_AGENT_PROVIDER`; compatible endpoint support is limited to `/models` and `/chat/completions`. |
| Planning | Intent matching/ranking and execution-plan data models | Not general model-driven planning. |
| Execution | Registered actions/tools; plan steps execute sequentially | No isolated execution environment. |
| Chat | Authenticated and guest conversations through `ChatService` | Non-streaming request/response; RAG is not wired into API chat. |
| Workflows | In-process DAG engine with bounded concurrency, retries, timeouts, cancellation, checkpoint callbacks, and approval gates | REST-created definitions and run snapshots, including approval/idempotency state, persist through `ChatStore`; interrupted runs fail closed on restart. Python callable workflows are not persisted, and execution is not coordinated across replicas. REST accepts only `value`, `context`, and `join` node types. |
| Memory | Conversation history in SQLite/PostgreSQL; JSON long-term memory; in-memory token-frequency vector store | No learned embeddings or durable shared vector index. |
| Coding workspace | Admin-only, workspace-scoped file inspection and proposals; explicit editor saves; patch review | The API persists owner-scoped pending proposals, permission mode, and hashed-actor audit events through `ChatStore`; applying proposals are invalidated on restart. No shell or external tool execution. |
| Plugins | Python module discovery and registration; included math plugin | Imports execute Python in-process; no sandbox or signed registry. |
| MCP | JSON-RPC-style protocol/server/client building blocks | Client transport is injected; no built-in stdio/HTTP transport or coding-agent invocation. |
| Realtime | Bounded in-process event bus and HTTP SSE | No WebSocket transport or cross-process event distribution. |
| Observability | In-process tracing/metrics adapters and health routes | Readiness checks the configured provider and database; `/metrics` remains a static up gauge with no exporter or production alerting. |
| Web search | Optional Brave Search, per-message opt-in and separate query terms | Requires server-side API key; live provider behavior depends on external service. |
| Media/training | None | Image/video generation and model training are not implemented. |

## Persistence and process boundaries

`ChatStore` supports SQLite for local/single-instance use and PostgreSQL for
shared chat/session and REST-workflow records. The PostgreSQL pool is capped
at 20 connections per process. Workflow definitions and run snapshots survive
restart; approval-waiting runs can resume, while runs interrupted in a
pending/running state are marked failed rather than replayed. Python callable
workflows are not serializable. Coding proposals and permission mode also use
`ChatStore`; pending proposals are owner-scoped, and an apply interrupted by
restart is invalidated rather than replayed. Coding permission mode (including
explicitly confirmed `auto`) survives restart. Execution coordination, event
subscribers, and rate-limit state remain process-local. This persistence does
not make multi-replica operation safe.

## Coding workspace limits

The workspace is enabled with `AI_AGENT_CODING_WORKSPACE`, includes the
configured root, direct child projects, and persisted administrator-selected
locations, and is admin-only. File listing is capped at 500 entries; requests
select at most 8 files, each at most 32 KiB,
with 80,000 characters maximum combined context. Proposals are manually
reviewed by default; auto-apply requires explicit confirmation. Editor saves
are user actions and use stale-content checks. HTML preview is sandboxed.
Sharing is opt-in, read-only, revocable, and expires after seven days.

## Authentication and configuration

Authentication uses configured static bearer tokens and token-to-subject
mapping. If authentication is not required and no tokens are configured,
local-development behavior can grant administrator access. Do not expose that
mode to untrusted networks. The API entry point now rejects a non-loopback
bind unless auth is explicitly required and at least one token is configured.
Boolean auth settings reject unknown values. The IP-based rate limiter is
process-local.

The default model provider is Ollama. Set `AI_AGENT_PROVIDER=openai_compatible`
to select the OpenAI-compatible adapter, with
`OPENAI_COMPATIBLE_BASE_URL`, `OPENAI_COMPATIBLE_MODEL`,
`OPENAI_COMPATIBLE_API_KEY`, and `OPENAI_COMPATIBLE_TIMEOUT` configured on the
server. Keys are not exposed to the browser; remote URLs require HTTPS when a
key is set. The adapter supports model listing and non-streaming Chat
Completions.

## Deployment maturity

Docker and Kubernetes examples exist. Kubernetes expects external PostgreSQL
and a provider endpoint (Ollama by default); manifests are examples, not
evidence of high availability.
GitHub Actions runs backend tests and the frontend build, but not secret
scanning or deployment validation. The tracked `.env` was removed from the
index in the current worktree, the local file was preserved, and ignore rules
were added; its contents were not read or copied. See
[Security and Governance](./SECURITY_AND_GOVERNANCE.md).
