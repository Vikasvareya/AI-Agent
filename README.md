# AI Agent Framework

An extensible Python agent framework with a chat API, workflow foundation,
and administrator coding workspace. The repository is evolving; some
components are prototypes or single-process implementations, and it is not
currently a proven high-traffic or high-availability platform.

## What exists today

- Python planning, execution, tool, memory, plugin, workflow, and MCP building
  blocks.
- A threaded HTTP API and health service.
- React chat with conversation persistence and configured-provider model
  discovery/switching (Ollama by default; OpenAI-compatible APIs also supported).
- A separate administrator coding workspace with scoped file access,
  explicit editor saves, reviewed patch proposals, project sessions, and
  optional read-only shares.
- Optional Brave web search using per-message opt-in and separate search
  terms.
- Docker Compose and Kubernetes deployment examples.

**Important boundaries:** Provider selection is per server, and the
OpenAI-compatible adapter supports non-streaming Chat Completions only.
Workflow and some coding/runtime state is process-local. Chat is
non-streaming; image/video generation and model training are not implemented.
Skills, marketplace installs, automation, shell execution, and coding-agent
plugin/MCP invocation are not available. See
[Current Implementation](./docs/CURRENT_IMPLEMENTATION.md) and
[Known Limitations](./docs/KNOWN_LIMITATIONS.md).

## Get started

Requirements: Python version compatible with `pyproject.toml`, Node/npm for
frontend builds, and a reachable Ollama instance for model-backed chat.

PowerShell from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -r requirements-chat.txt
python -m app.api.server_main
```

By default, the API listens on port `8081` and health routes on `8080`. Start
Ollama separately and configure its URL/model through the environment. The API
refuses a non-loopback bind unless `AI_AGENT_REQUIRE_AUTH=true` and at least
one API/admin/user token is configured. See [.env.example](./.env.example)
for local configuration keys; replace blank token values using a secure
source before startup.
`python main.py` starts the older interactive CLI, not the API.

For frontend verification:

```powershell
Set-Location frontend
npm ci
npm run build
```

See [API and Developer Guide](./docs/API_AND_DEVELOPER_GUIDE.md) and
[Deployment and Operations](./docs/DEPLOYMENT_AND_OPERATIONS.md) for detailed
setup.

GitHub Actions runs the backend suite and frontend build on pushes and pull
requests. It currently does not scan secrets or validate container/Kubernetes
deployments.

## Interfaces

- Workflow operator UI: `/`
- Chat: `/chat/`
- Administrator coding workspace: `/coding/` (requires an enabled workspace
  and administrator authorization)
- API: `/v1/...`
- Health: `/health/live`, `/health/ready` and related health-server routes

The coding workspace requires `AI_AGENT_CODING_WORKSPACE` to point to an
authorized directory. Manual patch review is the default. Do not expose
development authentication mode or send private files to a model provider
without authorization.

Web search requires `AI_AGENT_BRAVE_SEARCH_API_KEY`. Users opt in per message
and submit separate search terms; the chat prompt is not sent to Brave.

## Documentation

### Authoritative project guides

- [Project Vision](./docs/PROJECT_VISION.md)
- [Current Implementation](./docs/CURRENT_IMPLEMENTATION.md)
- [Architecture](./docs/architecture.md)
- [Product Roadmap](./docs/PRODUCT_ROADMAP.md)
- [ARES Research and Evolution](./docs/ARES_RESEARCH_EVOLUTION.md) — proposed
  only; no ARES capability is implemented
- [Technology Strategy](./docs/TECHNOLOGY_STRATEGY.md)
- [Security and Governance](./docs/SECURITY_AND_GOVERNANCE.md)
- [API and Developer Guide](./docs/API_AND_DEVELOPER_GUIDE.md)
- [Deployment and Operations](./docs/DEPLOYMENT_AND_OPERATIONS.md)
- [Testing and Quality](./docs/TESTING_AND_QUALITY.md)
- [Implementation Status](./docs/IMPLEMENTATION_STATUS.md)
- [Architecture Decisions and Observations](./docs/ARCHITECTURE_DECISIONS.md)
- [Known Limitations](./docs/KNOWN_LIMITATIONS.md)
- [Contributing](./docs/CONTRIBUTING.md)
- [Documentation Update Report](./docs/DOCUMENTATION_UPDATE_REPORT.md)

### Detailed guides

- [Coding Agent Workspace](./docs/coding-agent-workspace.md)
- [REST and chat API reference](./docs/19-api.md)
- [Deployment examples](./docs/22-deployment.md)
- [MCP protocol building blocks](./docs/mcp.md)
- [Module guide index](./docs/)

## Security notice

The tracked `.env` was removed from the Git index in the current worktree;
the local file was preserved and is now ignored. Its contents were not read
or reproduced. This does not erase prior commits: review repository/history
exposure and rotate any potentially exposed credentials. See
[Security and Governance](./docs/SECURITY_AND_GOVERNANCE.md) before deployment.

## License

No top-level `LICENSE` file was found during the documentation audit. Confirm
and add the intended license before redistribution; this README does not
assert a license.
