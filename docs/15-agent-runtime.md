# Agent Runtime

- `ChatAgent` connects the basic planner/executor flow.
- `ReActAgent` records a trace around a selected plan and can retry the same
  bounded plan after an execution failure.
- `ReflectiveAgent` evaluates result text using simple failure markers and
  retries the same plan a bounded number of times.
- `LongTermMemory` is a separate local JSON-backed component; its presence
  does not mean every agent automatically uses persistent memory.
- `CoordinatorAgent` can fan out a bounded set of permitted registered agents
  and aggregate results. Task and message records persist through `ChatStore`.
  Execution is synchronous and process-local until a durable worker boundary
  is implemented.

All runtime agents should follow the
[Shared Agent Constitution](./AGENT_CONSTITUTION.md). Specialized roles remain
separate: ChatAgent handles conversation, CodingAgent handles scoped patch
work, ReActAgent is a bounded retry trace, and ReflectiveAgent is a bounded
result check.

These are framework prototypes, not model-driven autonomous reasoning.
Recorded “thought” strings are implementation trace labels, not evidence of
private model reasoning. See [Current Implementation](./CURRENT_IMPLEMENTATION.md)
and [Known Limitations](./KNOWN_LIMITATIONS.md).
