# Glossary

- **Agent:** Runtime component that receives a prompt and coordinates planning,
  execution, context, or memory. Current agent implementations are bounded
  prototypes.
- **ARES:** Working label for a proposed research/evolution initiative. No
  expansion or implementation is established.
- **Chat session:** Persisted chat conversation, or a project-scoped coding
  session, depending on the API route.
- **Coding proposal:** Validated patch awaiting manual review or explicit
  workspace-scoped application.
- **MCP:** Model Context Protocol; this repository contains JSON-RPC-style
  protocol building blocks but no built-in transport integration.
- **Provider:** Adapter that sends model requests; the factory supports Ollama
  and an OpenAI-compatible Chat Completions endpoint.
- **RAG:** Retrieval-augmented generation; the current pipeline is connected
  to the CLI path, not API chat.
- **Workflow:** DAG of nodes executed by the in-process workflow engine.
- **Workspace root:** Configured filesystem boundary for the coding agent.

For status and details, see [Current Implementation](./CURRENT_IMPLEMENTATION.md).
