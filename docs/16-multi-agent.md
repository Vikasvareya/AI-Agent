# Multi-Agent System

The current multi-agent components provide a small in-process routing
prototype:

- `AgentRegistry` registers and resolves agents by name.
- `CoordinatorAgent` selects one agent: explicit name, a registered name
  found in the prompt, or the configured default.
- `SharedMemory` stores values and request/reply history in process memory.

The coordinator calls one target and returns its result. It does not fan out
to multiple agents, aggregate parallel results, persist shared state, or
provide durable handoffs. This is not a distributed multi-agent orchestration
service.

See [Product Roadmap](./PRODUCT_ROADMAP.md) for proposed durable execution
and governance work.
