# Workflow Engine

The in-process workflow engine executes DAG nodes with dependency ordering and
bounded parallelism. It supports retries, node timeouts, cancellation,
checkpoint callbacks, lifecycle state, idempotency, and approval gates with
approver information. The API service persists REST-created definitions and
run snapshots in the configured `ChatStore` (SQLite or PostgreSQL).

The REST workflow service exposes a restricted definition schema with `value`,
`context`, and `join` node types; it does not accept arbitrary Python through
HTTP. Python callers can create workflow objects with callable actions.

Approval-waiting runs, their initial context, node results, decisions, owner
digest, and idempotency key are restored after restart. A run found pending or
running at startup is marked failed and is not replayed, since node side
effects may already have occurred. The REST schema supports only `value`,
`context`, and `join` nodes; Python callable workflows are not persisted.

The engine and live execution remain process-local. There is no distributed
worker/lease boundary or cross-process event delivery, so this persistence is
for single-process restart recovery, not horizontal execution or high
availability. Checkpoint callbacks remain available to other integrations.

See [Current Implementation](./CURRENT_IMPLEMENTATION.md) and
[Product Roadmap](./PRODUCT_ROADMAP.md). Workflow participation and approval
are future foundations for the
[AI Brain Master Architecture](./AI_BRAIN_MASTER_ARCHITECTURE.md); they do not
constitute a Cognitive Core or distributed multi-agent runtime.
