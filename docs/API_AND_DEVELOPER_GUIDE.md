# API and Developer Guide

## Start locally

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -r requirements-chat.txt
python -m app.api.server_main
```

The API listens on `http://127.0.0.1:8081` by default; health endpoints listen
on port `8080`. Ollama is the default model provider. To select the
OpenAI-compatible adapter, set `AI_AGENT_PROVIDER=openai_compatible` and
configure the `OPENAI_COMPATIBLE_*` server environment variables. The
interactive CLI is
`python main.py`; it is not the API service. See
[Deployment and Operations](./DEPLOYMENT_AND_OPERATIONS.md) for environment
and container setup.

## Authentication

The API uses configured bearer tokens. Set `AI_AGENT_REQUIRE_AUTH=true` and
separate admin/user credentials before exposing the service. In
development-only mode, missing credentials with auth not required can result
in administrator access. Never expose that mode to untrusted networks.

The API entry point enforces this boundary at startup: non-loopback bind
addresses require auth to be explicitly enabled and at least one token to be
configured. Invalid boolean values fail startup instead of silently disabling
auth. Local loopback development may continue without tokens. See the safe
[`.env.example`](../.env.example).

Use placeholders in examples and keep actual credentials in an approved
secret store or process environment. Do not commit `.env` values.

## API groups

The current API includes:

- Workflow registration, creation, listing, run inspection, cancellation, and
  approval routes.
- Chat guest sessions, conversations, model discovery, capability listing,
  and message submission.
- Admin-only coding workspace projects, file reads/writes, sessions, shares,
  permission mode, patch proposals, and paginated audit records.
- Health/readiness endpoints and server-sent workflow events.

The detailed route list and payload examples are maintained in
[19-api.md](./19-api.md). The API currently has no generated OpenAPI document
or supported client SDK.

## Example request

With the API configured for bearer authentication:

```powershell
$headers = @{ Authorization = "Bearer <configured-user-token>" }
Invoke-RestMethod -Method Get `
  -Uri "http://127.0.0.1:8081/v1/chat/models" `
  -Headers $headers
```

Do not put real token values in shell history or shared logs.

## Persistence and behavior

Chat conversations, coding sessions, and REST-created workflow definitions
and run snapshots use the configured SQLite or PostgreSQL store. Approval-
waiting workflow runs recover after restart; interrupted pending/running runs
are marked failed without replay. Python callable workflows are not persisted,
and live execution is not coordinated across replicas. Coding proposals,
permission mode, and hashed-actor audit events also persist; applying
proposals are invalidated on restart. Permission updates are not synchronized
across live replicas. Administrators can inspect recent coding audit records
through a bounded read endpoint. Coding audit events are retained for 365 days
by default; `AI_AGENT_CODING_AUDIT_RETENTION_DAYS=0` disables automatic
pruning. Event subscribers and rate-limit state remain process-local. Chat
completion is non-streaming. The chat API does not currently use the CLI RAG
path.

The coding agent is an administrator tool for bounded file context and
validated proposals. It does not execute code or commands. Permission mode
defaults to manual; automatic application requires an explicit administrator
action and is still limited to the configured workspace.

## Useful source locations

- API bootstrap/routes: `app/api/server_main.py`,
  `app/api/http_server.py`
- Chat service/store: `app/chat/service.py`, `app/chat/store.py`
- Coding workspace: `app/agents/coding_agent.py`
- Workflows: `app/workflows/` and `app/api/workflow_service.py`
- UI: `frontend/chat-ui/`
- Tests: `tests/api/`, `tests/agents/`, `tests/workflows/`

Keep API and product claims aligned with
[Current Implementation](./CURRENT_IMPLEMENTATION.md) and
[Known Limitations](./KNOWN_LIMITATIONS.md).
