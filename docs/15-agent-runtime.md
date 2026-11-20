# Agent Runtime

- `ChatAgent` connects the basic planner/executor flow.
- `ReActAgent` records a trace around a selected plan and can retry the same
  bounded plan after an execution failure.
- `ReflectiveAgent` evaluates result text using simple failure markers and
  retries the same plan a bounded number of times.
- `LongTermMemory` is a separate local JSON-backed component; its presence
  does not mean every agent automatically uses persistent memory.

These are framework prototypes, not model-driven autonomous reasoning.
Recorded “thought” strings are implementation trace labels, not evidence of
private model reasoning. See [Current Implementation](./CURRENT_IMPLEMENTATION.md)
and [Known Limitations](./KNOWN_LIMITATIONS.md).
