# Technology Strategy

## Current choices

| Area | Current technology | Observed constraint |
| --- | --- | --- |
| Runtime | Python, standard-library threaded HTTP server | Threaded, process-local state; no proven throughput target. |
| Model provider | Ollama or OpenAI-compatible Chat Completions | One provider is selected per server; compatible adapter is non-streaming. |
| Chat persistence | SQLite or PostgreSQL | SQLite is local/single-instance; PostgreSQL pool is per process. |
| UI | React, TypeScript, Vite | Separate workflow operator UI also exists. |
| Workflows/events | In-process Python DAG engine, bounded event bus, HTTP SSE | No durable queue, cross-process event bus, or WebSocket transport. |
| Search | Optional Brave Search API | Server-side key and explicit separate query required. |
| Packaging | Docker and Docker Compose examples; Kubernetes manifests | Examples do not demonstrate high availability or production readiness. |

These are implementation observations, not endorsements of every choice for a
future production deployment.

## Strategy principles

- Keep provider APIs, persistence, execution, identity, and transport behind
  tested interfaces.
- Avoid premature microservice splits; establish service boundaries from
  measured scaling and fault-isolation needs.
- Use durable shared infrastructure only where lifecycle, recovery, or
  multi-instance consistency requires it.
- Make security and tenancy properties explicit in data models and APIs,
  rather than relying on UI restrictions.
- Prefer maintained, supported dependencies with pinned, reproducible builds
  and clear upgrade ownership.
- Select infrastructure through workload measurements, failure analysis, and
  operational cost—not through scale claims alone.

## Proposed evolution

1. Define supported deployment modes (developer-local, single-instance
   service, and any future multi-instance profile).
2. Select authentication/identity, audit, and secret-management mechanisms
   before expanding external integrations.
3. Decide durable workflow/job and event infrastructure based on recovery and
   throughput requirements.
4. Add provider adapters through a conformance suite and explicit capability
   descriptors.
5. Add retrieval/vector infrastructure only after evaluation datasets,
   provenance, retention, and tenant-isolation requirements exist.
6. Add isolated worker execution only if use cases justify the cost and the
   isolation boundary can be tested.

No database, queue, cloud, or vector-store vendor is selected by this
document. A change in that direction should include a written decision with
measured requirements, migration/rollback strategy, security review, and
operational ownership.
