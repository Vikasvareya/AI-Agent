# Implementation Status

Status reflects repository code and tests inspected for this documentation
update. “Implemented” does not mean production-ready.

The target identity is **AI Brain**, but the repository is currently a
foundation. See [AI Brain Master Architecture](./AI_BRAIN_MASTER_ARCHITECTURE.md)
and [Shared Agent Constitution](./AGENT_CONSTITUTION.md).

| Capability | Status | Notes |
| --- | --- | --- |
| Python framework and CLI | Implemented foundation | `main.py` is an older interactive CLI; not the HTTP API. |
| Planner and executor | Limited implementation | Intent ranking and action dispatch exist; not a general autonomous planner. |
| Executor v2 lifecycle | Implemented foundation | PlanningGraph owns dependency/ID/cycle validation; execution is sequential and fail-fast; completed/failed plans cannot replay. |
| Model providers | Implemented foundation | Ollama and OpenAI-compatible Chat Completions; one selected per server, no streaming. |
| Chat API and UI | Implemented foundation | Guest/authenticated conversations and persistence; responses are non-streaming. |
| Unified chat Agent Runtime | Implemented foundation | HTTP and terminal chat use shared planning/executor composition; Time and calculator intents execute tools without provider calls. |
| Persistent profile memory | Implemented foundation | Structured owner-scoped SQLite/PostgreSQL records, explicit/casual capture, confirmation, CRUD API, and relevant runtime retrieval. |
| Memory correction history | Implemented foundation | Corrections can be proposed and confirmed through chat; confirmed value changes preserve previous/new values in owner-scoped history. |
| Resume draft management | Implemented foundation | Owner-scoped text resume draft CRUD and text export; editing and approval statuses are supported, PDF/DOCX is not. |
| Timezone-aware time tool | Implemented foundation | IANA locations and configured timezone defaults use `zoneinfo`; daylight saving is handled by the standard database. |
| Generalized timezone resolution | Implemented foundation | Country/city aliases and IANA identifiers resolve deterministically; ambiguous countries request clarification. |
| Contextual time follow-ups | Implemented foundation | Structured current-time action/location/tool context supports location changes, pronoun-like ellipsis, explicit tool reuse, and unrelated-context reset. |
| Safe calculator comparisons | Implemented foundation | AST arithmetic/comparison expressions preserve `=` and `==`; unsafe code and malformed expressions are rejected. |
| Workflow engine | Implemented with bounded restart recovery | REST-created definitions/run snapshots, approvals, idempotency, and hashed owner identities persist through `ChatStore`; interrupted runs fail closed. Execution is still in-process; Python callable workflows and multi-replica coordination are unsupported. |
| Chat persistence | Implemented | SQLite and PostgreSQL; PostgreSQL pool is per process. |
| API bind/auth guard | Implemented baseline | Loopback development is allowed; non-loopback binds require explicit auth and at least one configured token. Tokens remain static configuration. |
| Coding workspace | Implemented with boundaries | Admin-only, workspace-scoped editor/proposals/sessions/shares; API proposals and permission mode persist through `ChatStore`, with hashed-actor audit events, bounded admin audit queries, and fail-closed recovery for interrupted applies. |
| Long-term memory | Limited | JSON file persistence; lifecycle and multi-tenant controls are not established. |
| Vector memory | Prototype | In-memory normalized token-frequency vectors, not learned embeddings. |
| RAG | Limited | Connected to CLI chat path; not integrated into API chat service. |
| Multi-agent coordination | Implemented foundation | Structured, permission-controlled fan-out delegates tasks to registered agents, persists task/message records in SQLite/PostgreSQL, and aggregates results; it remains synchronous and single-process for execution. |
| Durable agent task queue | Implemented foundation | SQLite/PostgreSQL queue with worker leases, stale-lease recovery, bounded retries, and owner-scoped cancellation; worker execution is process-local until separately distributed/operated. |
| Plugins | Limited | Python module loader and math plugin; no sandbox or signed registry. |
| MCP | Protocol building blocks | JSON-RPC-style client/server code; no built-in transport or coding-agent integration. |
| Realtime | Limited | In-process bounded event bus and HTTP SSE; no WebSocket or cross-process fan-out. |
| Live chat activity | Implemented foundation | Owner-scoped persisted chat activity events replay through HTTP/SSE and render in the chat timeline; provider response streaming is not implemented. |
| Unified web research | Implemented foundation | Brave and SearXNG provider adapters, auto/fallback routing, normalized/deduplicated results, provider status, and bounded SSRF-safe page fetching. |
| Observability | Prototype | Readiness checks database and configured provider endpoint availability; metrics remain a static up gauge. |
| Web search | Optional integration | Brave Search requires server-side configuration and per-message opt-in. |
| Image/video generation | Not implemented | UI reports unsupported capability. |
| Model training/fine-tuning | Not implemented | No dataset, training, evaluation, or deployment pipeline. |
| CI automation | Basic workflow implemented | GitHub Actions runs backend tests, frontend build, full-history Gitleaks, Compose validation/container build/startup smoke test, and Kubernetes schema validation; it does not deploy to a cluster. |
| ARES | Proposed only | No ARES runtime, service, package, configuration, or tests. |
| High-availability production profile | Not established | Process-local state and lack of load/failover evidence prevent this claim. |

## AI Brain system matrix

| AI Brain system | Status | Evidence |
| --- | --- | --- |
| Perception — text/chat | Partial | Chat and selected-file context exist; general multimodal and sensor input do not |
| Reasoning | Prototype | Rule/intent planning plus bounded ReAct/reflective agents |
| Memory | Prototype/partial | Conversation persistence, JSON memory, vector memory, and shared-memory prototype |
| Executive/goal management | Not implemented | Planning and workflow foundations exist, but no goal engine or cross-agent executive |
| Learning | Not implemented | No verified memory-to-policy learning or model-weight training |
| Social/multi-agent | Prototype | Name routing and process-local shared memory only |
| Autonomous research | Partial | Optional Brave Search and citation support; no research agent or verified evidence registry |
| Temporal intelligence | Not implemented | No historical, live monitoring, forecasting, or scenario engine |
| Self-repair | Partial | Scoped patch proposals and fail-safe recovery; no autonomous controlled repair |
| Innovation/capability creation | Not implemented | No capability detector, tool factory, or experiment registry |
| Model intelligence | Not implemented | Provider inference exists; no training or model lifecycle Studio |
| Safety/governance | Partial | Authentication, workspace scoping, approvals, audit foundations; no complete managed RBAC/sandbox |
| Dynamic skills | Not implemented | No governed skill registry or skill factory |
| Autonomous tools | Not implemented | No generated-tool factory or isolated tool execution |
| Programming-language engineering | Experimental/research | No implementation or language runtime |
| Robotics/physical intelligence | Not implemented | No hardware integration or actuation |
| Autonomous evolution | Not implemented | No production self-modification or controlled continuous-evolution runtime |

For detailed definitions and caveats, see
[Current Implementation](./CURRENT_IMPLEMENTATION.md),
[Known Limitations](./KNOWN_LIMITATIONS.md), and
[Product Roadmap](./PRODUCT_ROADMAP.md).
