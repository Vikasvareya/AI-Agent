# Repository Structure

The repository is organized by runtime concern:

```text
app/
  agents/        Agent registry, coordinator, coding and reasoning prototypes
  api/           HTTP server, chat/workflow services and routes
  chat/          Chat service, persistence and optional web search
  context/       Conversation context and resolution
  executor/      Action execution and handlers
  health/        Liveness, readiness and metrics endpoints
  mcp/           MCP-style protocol/client/server building blocks
  memory/        Conversation, long-term, vector memory and RAG
  observability/ In-process tracing and metrics
  planner/       Intents, plans and planning data models
  plugins/       Plugin base and module discovery
  providers/     Provider interface and Ollama implementation
  realtime/      Event bus and workflow event models
  tools/         Built-in tools and tool registry
  workflows/     DAG workflow models and engine
frontend/
  chat-ui/       React, TypeScript and Vite application
tests/           Pytest tests organized by subsystem
deploy/          Example Kubernetes manifests
docs/             Authoritative and module-level documentation
```

The exact tree evolves. `main.py` is the older interactive CLI; the default
HTTP API entry point is `app.api.server_main`.
