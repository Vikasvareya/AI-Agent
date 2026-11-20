# Product Roadmap

This roadmap is capability- and evidence-based, not date-based. Every item
below is planned unless explicitly marked **Current**. A milestone is complete
only when its acceptance criteria are met and its status is updated in
[Implementation Status](./IMPLEMENTATION_STATUS.md).

## Current foundation — partially implemented

**Current:** Python framework modules, Ollama integration, chat/API, workflow
operator UI, React chat, admin coding workspace, local persistence, and
example Compose/Kubernetes manifests.

**Acceptance evidence:** focused tests pass; frontend build succeeds; API and
health behavior is documented; security-sensitive routes and filesystem
boundaries have regression coverage.

**Remaining:** resolve secret hygiene, increase test/CI discipline, establish
reproducible deployment validation, and document supported environments.

**Progress in the current worktree:** the API now defaults to loopback binding
and refuses non-loopback binding unless auth and a token are configured.
Tracked `.env` removal is staged and the local file is preserved/ignored.
Review and rotate any credentials already present in repository history;
the index change does not rewrite history. A basic hosted CI workflow now runs
backend tests and the frontend build; secret scanning and deployment validation
remain.

## P0 — Secure baseline and single-instance reliability

**Depends on:** current API and deployment foundation.

- Remove credentials from tracked files/history, add robust secret exclusion,
  rotate any potentially exposed values, and add a safe configuration example.
- Require explicit secure authentication in non-development deployments;
  document token rotation and recovery.
- Add durable audit records for privileged actions and make permission changes
  explicit and observable.
- Add deployment smoke tests and health checks that verify required
  dependencies rather than returning a static success signal.

**Acceptance:** secret scanning is clean; no privileged production route is
reachable without configured identity; audit records survive restart; failure
of required dependencies is reflected by readiness; runbooks define backup,
restore, and credential rotation.

## P1 — Durable execution and horizontal consistency

**Depends on:** P0 identity, security, and database decisions.

- Extend durable audit coverage, define retention/export controls, and add
  audit query tooling. The server now persists coding proposals, permission
  mode, and coding action records; REST workflow definitions/run snapshots
  also persist through `ChatStore`, while Python callable workflows do not.
- Add a durable queue/worker boundary and cross-process coordination with
  cancellation and retry semantics; restart snapshots alone do not enable
  horizontal execution.
- Replace process-local rate limiting and event delivery with shared
  infrastructure.
- Define ownership and tenant scoping for every persistent resource.

**Acceptance:** requests can be routed to any replica without losing run,
approval, proposal, or rate-limit state; restart/recovery behavior is tested;
tenant-isolation tests cover cross-account reads and writes.

## P2 — Provider and extension ecosystem

**Depends on:** stable provider/tool contracts and P0 security controls.

- Add independently tested provider adapters and explicit model capability
  metadata.
- Define reviewed plugin manifests, versioning, dependency policy, and
  isolation; keep untrusted extensions out of the API process.
- Implement real MCP transports with per-server/tool scopes, timeouts, and
  audit controls.
- Add a governed skills catalog and invocation permissions.

**Acceptance:** provider conformance tests pass; plugin/MCP calls are scoped,
time-bounded, attributable, and denied by default; failure and revocation tests
are in place.

## P3 — Evaluated retrieval and agent execution

**Depends on:** P0 safety and P1 durable jobs.

- Integrate RAG into API chat only with explicit source provenance and
  tenant-aware retrieval.
- Evaluate memory quality, retrieval relevance, prompt-injection resistance,
  and task outcomes against versioned datasets.
- If code execution is added, run it in isolated workers with resource,
  network, filesystem, and approval controls.

**Acceptance:** repeatable evaluation baselines and regression thresholds are
published; retrieved data is tenant-scoped and cited; code execution cannot
reach host credentials or unrestricted network/filesystem resources.

## P4 — Production operations and scale

**Depends on:** P0–P3 as applicable.

- Define SLOs, alerting, tracing/metrics export, capacity limits, and incident
  runbooks.
- Load, soak, failover, backup/restore, and chaos-test the supported topology.
- Establish release, rollback, migration, and compatibility policies.

**Acceptance:** measured capacity and recovery objectives are published; all
production dependencies have dashboards and actionable alerts; deployment and
rollback are rehearsed.

## ARES track

ARES is a proposed research/evolution initiative, not an implemented
subsystem. Its scope and stages are described in
[ARES Research and Evolution](./ARES_RESEARCH_EVOLUTION.md); no ARES work is
counted as complete until separately specified and tested.
