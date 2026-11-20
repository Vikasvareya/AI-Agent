# Implementation Status

Status reflects repository code and tests inspected for this documentation
update. “Implemented” does not mean production-ready.

| Capability | Status | Notes |
| --- | --- | --- |
| Python framework and CLI | Implemented foundation | `main.py` is an older interactive CLI; not the HTTP API. |
| Planner and executor | Limited implementation | Intent ranking and action dispatch exist; not a general autonomous planner. |
| Model providers | Implemented foundation | Ollama and OpenAI-compatible Chat Completions; one selected per server, no streaming. |
| Chat API and UI | Implemented foundation | Guest/authenticated conversations and persistence; responses are non-streaming. |
| Workflow engine | Implemented with bounded restart recovery | REST-created definitions/run snapshots, approvals, idempotency, and hashed owner identities persist through `ChatStore`; interrupted runs fail closed. Execution is still in-process; Python callable workflows and multi-replica coordination are unsupported. |
| Chat persistence | Implemented | SQLite and PostgreSQL; PostgreSQL pool is per process. |
| API bind/auth guard | Implemented baseline | Loopback development is allowed; non-loopback binds require explicit auth and at least one configured token. Tokens remain static configuration. |
| Coding workspace | Implemented with boundaries | Admin-only, workspace-scoped editor/proposals/sessions/shares; API proposals and permission mode persist through `ChatStore`, with hashed-actor audit events, bounded admin audit queries, and fail-closed recovery for interrupted applies. |
| Long-term memory | Limited | JSON file persistence; lifecycle and multi-tenant controls are not established. |
| Vector memory | Prototype | In-memory normalized token-frequency vectors, not learned embeddings. |
| RAG | Limited | Connected to CLI chat path; not integrated into API chat service. |
| Multi-agent coordination | Prototype | Routes to one named/default agent; no fan-out or durable handoff. |
| Plugins | Limited | Python module loader and math plugin; no sandbox or signed registry. |
| MCP | Protocol building blocks | JSON-RPC-style client/server code; no built-in transport or coding-agent integration. |
| Realtime | Limited | In-process bounded event bus and HTTP SSE; no WebSocket or cross-process fan-out. |
| Observability | Prototype | Readiness checks database and configured provider endpoint availability; metrics remain a static up gauge. |
| Web search | Optional integration | Brave Search requires server-side configuration and per-message opt-in. |
| Image/video generation | Not implemented | UI reports unsupported capability. |
| Model training/fine-tuning | Not implemented | No dataset, training, evaluation, or deployment pipeline. |
| CI automation | Basic workflow implemented | GitHub Actions runs backend tests, frontend build, full-history Gitleaks, Compose validation/container build/startup smoke test, and Kubernetes schema validation; it does not deploy to a cluster. |
| ARES | Proposed only | No ARES runtime, service, package, configuration, or tests. |
| High-availability production profile | Not established | Process-local state and lack of load/failover evidence prevent this claim. |

For detailed definitions and caveats, see
[Current Implementation](./CURRENT_IMPLEMENTATION.md),
[Known Limitations](./KNOWN_LIMITATIONS.md), and
[Product Roadmap](./PRODUCT_ROADMAP.md).
