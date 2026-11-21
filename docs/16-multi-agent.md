# Multi-Agent System

The current multi-agent components provide a small in-process routing
prototype:

- `AgentRegistry` registers and resolves agents by name.
- `CoordinatorAgent` selects one agent: explicit name, a registered name
  found in the prompt, or the configured default.
- `SharedMemory` stores values and request/reply history in process memory.

The coordinator can route to one agent or fan out to a bounded set of
registered agents. Each delegation creates owner-scoped task records and
structured sender/recipient messages in `ChatStore`, and the response includes
a completed/partial/failed aggregation. User and admin permissions are checked
through an explicit policy before execution.

Execution can now be requested as durable work with `{"async": true}`. Tasks
use a persisted queue, in-process workers, bounded leases, stale-leases
recovery, bounded retries, and owner-scoped cancellation. Synchronous
delegation remains available for compatibility. Cross-replica worker ownership
is database-backed, but production horizontal scaling still requires replica
coordination and operational testing.

Agent roles and communication principles are governed by the
[Shared Agent Constitution](./AGENT_CONSTITUTION.md). Future structured
delegation, parallel execution, review, and result aggregation are roadmap
capabilities, not current behavior.

See [Product Roadmap](./PRODUCT_ROADMAP.md) for proposed durable execution
and governance work.
