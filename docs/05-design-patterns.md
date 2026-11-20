# Design Patterns in the Current Code

This guide describes patterns visible in the implementation, not a guarantee
that every module is fully abstracted.

- **Factory:** `ProviderFactory` creates the configured Ollama or
  OpenAI-compatible model provider.
- **Registry:** intents, tools, and agents are registered and resolved through
  registries.
- **Strategy/interface seams:** provider, planner, executor, context resolver,
  memory, and tool base classes permit alternate implementations.
- **Dependency injection:** selected agent/runtime components receive
  collaborators through constructors.
- **DAG execution:** the workflow engine schedules nodes by dependencies;
  this is distinct from the sequential plan executor.

The interface seams are extension points, not proof of provider portability,
plugin isolation, or production-ready dependency injection. See
[Architecture Decisions](./ARCHITECTURE_DECISIONS.md).
