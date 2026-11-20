# Known Limitations

This list describes current constraints, not a complete security assessment.
See [Security and Governance](./SECURITY_AND_GOVERNANCE.md) for risks and
required controls.

## Runtime and scaling

- The API is a standard-library threaded HTTP server, not a measured
  high-throughput service.
- REST-created workflow definitions and run snapshots persist through
  `ChatStore`, but workflow execution and event delivery are process-local.
  Approval-waiting runs recover; pending/running runs are marked failed rather
  than replayed. Python callable workflows are not persisted.
- Coding proposals and permission mode persist through `ChatStore` in the
  server configuration, and proposal decisions are audited with hashed actor
  identities. An apply interrupted during restart is invalidated, not
  replayed. Permission updates are not synchronized to already-running
  replicas; audit retention and a read/export API are not implemented.
- Event subscribers and rate-limit state remain in process memory.
- The IP rate limiter is not distributed; concurrent replicas do not share
  its counters.
- PostgreSQL persists chat/session and REST-workflow records; its connection
  pool is per-process and capped at 20. The database does not coordinate
  workers or make multi-replica execution safe.
- Health `/metrics` returns a static up gauge rather than comprehensive
  application telemetry.
- No load, soak, failover, or chaos evidence establishes production capacity.

## Models, agents, and retrieval

- Ollama is the only provider created by the provider factory.
- Planner intent selection is largely rule/registry based. ReAct and
  reflective agents are bounded prototypes, not general model-driven
  autonomous reasoning.
- The multi-agent coordinator selects a single agent; it does not provide
  parallel fan-out or durable task handoffs.
- Vector memory uses normalized token-frequency vectors in process memory;
  it is not an embedding database.
- RAG is connected to the CLI path, not API chat.
- Image/video generation and model training/fine-tuning are not implemented.

## Coding workspace and integrations

- The coding workspace is admin-only and confined to a configured root and
  direct child projects. Files/context are bounded; see
  [coding-agent-workspace.md](./coding-agent-workspace.md) for exact limits.
- No shell, command, or arbitrary code execution is available.
- API-created proposal and permission state is stored in `ChatStore`;
  standalone `CodingAgent` instances without a store remain process-local.
  Auto-apply is workspace-limited and its permission changes/applications are
  audited, but there is no audit retention policy or query API.
- Plugins import Python code in-process; no sandbox or signed registry exists.
- MCP has protocol building blocks but no built-in stdio/HTTP transport and is
  not invoked by the coding agent.
- Skill installation, marketplace, and automation capabilities are not
  implemented.
- Brave Search requires a server key and separate user-supplied query; the
  live integration is unavailable when no key is configured.

## Security and operations

- Authentication uses static bearer-token configuration, not managed identity
  or full RBAC. A permissive local-development mode can grant admin when auth
  is disabled and no tokens exist; the API server now permits that mode only
  for loopback binds.
- The tracked `.env` was removed from the index in the current worktree and
  local ignore rules were added; its contents were not read. This does not
  erase prior commits. Review repository/history exposure and rotate
  potentially exposed credentials.
- Kubernetes and Docker assets are examples, not evidence of a hardened
  production deployment.
- CI currently runs backend tests and the frontend build only; there is no
  secret scanner, container build, Kubernetes validation, or load test job.
- There is no generated OpenAPI specification or supported SDK.
- License metadata is inconsistent: README previously said MIT, but no
  top-level `LICENSE` file was found during this audit. Confirm licensing
  before redistribution.
- ARES has no implementation; all ARES capabilities are proposals.
