# REST API

The REST layer exposes workflows through the framework-neutral
`WorkflowAPIService`.

REST-created workflow definitions and run snapshots are stored in the same
SQLite/PostgreSQL `ChatStore` used for chat and coding sessions. Approval-
waiting runs and idempotency are restored after restart; interrupted
pending/running runs are marked failed instead of replayed. Run ownership is
persisted as a digest, not a bearer token. This is restart recovery for the
current in-process API, not distributed execution; Python callable workflows
are not persisted.

This is the detailed route reference. For onboarding and current trust/state
boundaries, see [API and Developer Guide](./API_AND_DEVELOPER_GUIDE.md) and
[Current Implementation](./CURRENT_IMPLEMENTATION.md).

## Resources

- List registered workflows
- Admin: create a workflow definition
- User/admin: create a workflow run
- User: list and inspect their own runs
- Admin: inspect any run
- User/admin: cancel their own run
- Admin: cancel any run and approve/reject workflow nodes
- Inspect authenticated session role

## Error Contract

API errors contain:

- Stable error code
- Human-readable message
- HTTP-compatible status code

Examples include `WORKFLOW_NOT_FOUND`, `RUN_NOT_FOUND`,
`RUN_NOT_CANCELLABLE`, and `INVALID_APPROVAL`.

## Workflow Events

Workflow lifecycle updates are published as typed events:

- `workflow.status`
- Run-specific or all-run subscriptions
- Bounded subscriber buffers
- HTTP Server-Sent Events (SSE) streaming

No WebSocket or cross-process event transport is implemented.

## HTTP Transport

The stdlib HTTP transport provides:

- Bearer-token authentication
- Per-client sliding-window rate limiting
- REST run and approval resources
- Server-sent event streaming
- JSON error responses

## Conversational Chat

The React chat application is served at `/chat/`; the workflow control plane
remains at `/`. Both use the same-origin API on port 8081. Chat completion uses
the configured `BaseProvider` implementation (Ollama by default) and returns a
JSON response after generation; token streaming is not implemented yet.

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/v1/chat/guest-sessions` | Start or resume an anonymous browser session |
| `GET` | `/v1/chat/models` | List models installed in the configured provider |
| `GET` | `/v1/chat/capabilities` | List available chat modes and unsupported capabilities |
| `GET` | `/v1/coding/projects` | List the workspace root and eligible project folders (admin) |
| `GET` | `/v1/coding/directories?path={absolute-path}` | Browse server directories for project selection (admin) |
| `POST` | `/v1/coding/projects` | Create a project in the configured workspace or selected parent directory (admin) |
| `POST` | `/v1/coding/projects/import` | Add an existing server directory as a project (admin) |
| `DELETE` | `/v1/coding/projects/{id}` | Delete a workspace child project or remove an external project link, with its saved conversations and associated pending proposals (admin) |
| `GET` | `/v1/coding/status` | Check whether the project coding agent is configured |
| `GET` | `/v1/coding/files?project={id}` | List eligible project files (admin) |
| `GET` | `/v1/coding/file?path={path}` | Read an eligible project file (admin) |
| `POST` | `/v1/coding/file` | Explicitly create or save an eligible text file (admin) |
| `GET` | `/v1/coding/models` | List models available to the coding workspace |
| `GET` | `/v1/coding/permissions` | Read the current coding permission mode |
| `POST` | `/v1/coding/permissions` | Select manual review or explicitly confirmed auto-apply |
| `GET` | `/v1/coding/audit?limit=50&offset=0` | Read paginated coding audit events (admin only; limit 1-100, offset 0-10000) |
| `GET` | `/v1/audit?limit=50&offset=0` | Read paginated privileged-action audit events (admin only; limit 1-100, offset 0-10000) |
| `GET` | `/v1/audit/export?format=csv&limit=100` | Export bounded JSON or CSV audit data (admin only; limit 1-1000) |
| `GET` | `/v1/audit/summary` | Return audit action counts and security-sensitive event summary (admin only) |
| `POST` | `/v1/auth/credentials` | Create an expiring role credential (admin only) |
| `GET` | `/v1/auth/credentials` | List credential metadata and active/expired/revoked status (admin only) |
| `POST` | `/v1/auth/credentials/{id}/rotate` | Revoke a credential and issue its replacement (admin only) |
| `DELETE` | `/v1/auth/credentials/{id}` | Revoke an active credential (admin only) |
| `GET` | `/v1/coding/proposals` | List the caller's pending proposals, including recovered proposals |
| `GET` | `/v1/coding/integrations` | Report skill, plugin, MCP, and training availability |
| `GET` | `/v1/coding/sessions?project={id}` | List the caller's project sessions (admin) |
| `POST` | `/v1/coding/sessions` | Create a persistent project session (admin) |
| `GET` | `/v1/coding/sessions/{id}` | Read a session and up to 100 recent messages (admin) |
| `DELETE` | `/v1/coding/sessions/{id}` | Delete a session, its messages, share links, and associated pending proposals (admin) |
| `POST` | `/v1/coding/sessions/{id}/share` | Create an explicit seven-day read-only share link (admin) |
| `DELETE` | `/v1/coding/sessions/{id}/shares` | Revoke all share links for a session (admin) |
| `GET` | `/v1/coding/shared/{token}` | Read a shared session with its unguessable token |
| `POST` | `/v1/coding/proposals` | Generate a validated workspace patch proposal |
| `POST` | `/v1/coding/proposals/{id}/apply` | Apply a pending patch after manual review |
| `POST` | `/v1/coding/proposals/{id}/reject` | Reject a pending patch |
| `GET` | `/v1/chat/conversations` | List the caller's conversations |
| `POST` | `/v1/chat/conversations` | Create a conversation (`title` optional) |
| `GET` | `/v1/chat/conversations/{id}` | Read up to 100 recent messages |
| `DELETE` | `/v1/chat/conversations/{id}` | Delete a conversation and its messages |
| `POST` | `/v1/chat/conversations/{id}/messages` | Send a message and receive the assistant reply |

Coding audit records are returned newest-first. The endpoint accepts `limit`
from 1 to 100 and `offset` from 0 to 10,000, and includes a `has_more` flag.
Actor identifiers are digests rather than bearer tokens. Records are retained
for 365 days by default; set `AI_AGENT_CODING_AUDIT_RETENTION_DAYS=0` to
disable automatic pruning.
General privileged-action audit records are available from `/v1/audit` with
the same pagination limits and actor-digest rules. Set
`AI_AGENT_AUDIT_RETENTION_DAYS=0` to disable general audit pruning.

The model catalog comes from the selected provider: installed Ollama models or
the configured OpenAI-compatible `/models` endpoint. It contains the provider
default and stable model IDs suitable for message requests. The provider caches
the catalog for up to 30 seconds;
`GET /v1/chat/models?refresh=true` bypasses that cache.

```json
{
  "provider": "ollama",
  "default_model": "llama3.2",
  "models": [
    {
      "id": "llama3.2:latest",
      "name": "llama3.2:latest",
      "provider": "ollama"
    }
  ]
}
```

`GET /v1/chat/capabilities` reports `chat` and `coding` as available. Coding
mode adds coding-focused instructions to the model prompt; it does not execute
code or provide a sandbox. Image and video modes are reported as unavailable
until generation providers are configured. `web_search` is available only
when `AI_AGENT_BRAVE_SEARCH_API_KEY` is configured.

### Project Coding Agent

The coding workspace is a separate dashboard at `/chat/coding/`, distinct from
the chat's Coding prompt mode and the workflow operator console. It is available
only to administrators and only when `AI_AGENT_CODING_WORKSPACE` points to an
existing workspace directory. It lists eligible source files and reads only
1–8 files explicitly selected by the administrator. The file browser is capped
at 500 entries; each selected file is limited to 32 KiB and combined context to
80,000 characters. Environment, credential, key, and generated dependency
files are excluded. The model request timeout defaults to 180 seconds and can
be changed with `AI_AGENT_CODING_TIMEOUT`.

Generate a proposal with:

```json
{
  "task": "Add input validation to this function.",
  "files": ["src/example.py"],
  "model": "llama3.2:latest",
  "project_id": ".",
  "session_id": "optional-coding-session-id"
}
```

`model`, `project_id`, and `session_id` are optional; they default to the
configured model, workspace root, and no session respectively. When a session
is provided, its recent messages are stored and used as bounded context.
Proposals are checked
for safe workspace-relative paths, selected-file scope, line counts, and exact
source context. The response includes `proposal_id`, `permission_mode`,
`status`, and `applied`.

Permission mode defaults to `manual`. A manual proposal remains pending until
an administrator reviews it and calls `/v1/coding/proposals/{id}/apply` or
`/reject`. Applying rechecks that each source file still matches the version
used to generate the proposal; stale proposals are rejected. New files can be
created in existing project directories. Administrators can create projects in
selected server-side locations or add existing directories. Deleting a child
of the configured workspace permanently removes its folder; removing an
external project only removes its registration and saved conversations. The
workspace root cannot be deleted. Conversation deletion removes its messages
and invalidates its share links. Individual file deletion, renames, nested
directory creation, shell commands, and external tool execution are not
supported.

`POST /v1/coding/projects` accepts `{"name":"my-project"}` and optionally a
server-side `parent_path` absolute path. Existing directories can be registered
with `POST /v1/coding/projects/import` using `{"path":"..."}`. File creation uses
`POST /v1/coding/file` with `{"path":"my-project/main.py","content":"...","create":true}`.
Saving an existing file requires the original content returned by the read
endpoint:

```json
{
  "path": "my-project/main.py",
  "content": "print('updated')\n",
  "expected_content": "print('hello')\n",
  "create": false
}
```

The service rejects a save if the file changed since it was opened. The editor
and agent proposals share the allowlist and path restrictions, but an explicit
editor Save is a user-authorized write and does not create an agent proposal.

Projects are filesystem folders, not arbitrary machine paths. Existing direct
child folders are listed automatically, along with the workspace root. File
reads and writes remain subject to the coding agent's allowlist and 32 KiB
per-file limit. HTML preview runs in a sandbox with scripts and external
resources blocked.

Coding sessions and their latest 100 messages are persisted in the configured
chat database. Proposal generation can pass the latest 12 messages (at most
16,000 characters) as untrusted context. Session data is scoped to the current
administrator credential identity and project. A share link is created only
after an explicit action, exposes prompts/proposals read-only to anyone holding
the link, expires after seven days, and can be revoked with the shares endpoint.
The create response returns the token once with `expires_at`; only a hash of
the share token is stored.

### Optional web search

Send a message with both `web_search: true` and a separate `search_query`.
Search queries are limited to 400 characters. Only the separate terms are sent
to Brave Search; the chat prompt is not. Common credentials and source-code
patterns are rejected, but do not enter private information. Search results
are treated as untrusted evidence, and cited URLs are appended to the
assistant's response. Search remains disabled when no Brave API key is
configured.

```json
{
  "content": "Summarize the current documentation.",
  "client_message_id": "a-client-generated-unique-id",
  "web_search": true,
  "search_query": "official product documentation"
}
```

Enable automatic application only after an explicit admin confirmation:

```json
{
  "mode": "auto",
  "confirm_auto_apply": true
}
```

In `auto` mode, each validated proposal is written immediately, but only to
the configured workspace and selected/approved proposal paths. Auto mode does
not run shell commands or invoke plugins or MCP tools. Set `{"mode":"manual"}`
to restore review-before-write. Permission mode and pending proposals are
stored in `ChatStore` by the server; use `GET /v1/coding/proposals` to recover
pending proposals. An apply interrupted during restart is invalidated rather
than replayed. A standalone coding-agent instance without a store remains
process-local.

`GET /v1/coding/integrations` is an availability report, not a tool-execution
API. The current coding agent does not have a skill registry, connected MCP
servers, or plugin invocation enabled. Model training and dataset management
are not implemented; installed provider models can be selected. Keep the
configured workspace limited to code the administrator is authorized to share
with the configured model provider. See
[the coding workspace guide](./coding-agent-workspace.md).

A message request is:

```json
{
  "content": "Hello",
  "client_message_id": "a-client-generated-unique-id",
  "model": "llama3.2:latest",
  "mode": "chat"
}
```

`model` is optional and defaults to the selected provider's configured model.
Explicit model IDs must appear in the model catalog. `mode` is optional and accepts `chat` or
`coding`; requests for unsupported modes, including `image` and `video`, return
HTTP 501 with `CAPABILITY_UNAVAILABLE`. An unavailable model returns HTTP 400
with `MODEL_NOT_FOUND`.

Messages are limited to 8,000 characters. The client ID makes retries
idempotent for a conversation; reusing it with different text returns HTTP 409.
The model receives the latest 20 completed messages plus the new user message.
Conversation access is scoped to the hash of the bearer credential or
guest-session cookie; raw credentials are not stored in the chat database.
For multi-user integrations, configure `AI_AGENT_USER_TOKENS` as a JSON object
mapping each bearer token to a stable, tenant-qualified subject, for example
`{"service-user-token":"tenant-42:user-17"}`. Token rotation can retain
history by retaining the same subject. The legacy `AI_AGENT_USER_TOKEN` maps
all of its holders to one shared identity and must not be shared across
independent users or tenants.

Guests receive an opaque, `HttpOnly`, `SameSite=Strict` cookie, valid for 30
days. Set `AI_AGENT_COOKIE_SECURE=true` when serving through HTTPS. Account
users use the existing bearer tokens. Guest and account conversation histories
are separate. The public guest-session endpoint and chat API are subject to the
existing per-process IP rate limiter.
External applications can integrate through these versioned REST endpoints
using their own bearer token; the browser frontend is not required.

The default local database is `data/chat.sqlite3` (SQLite WAL). SQLite is for
local or single-instance use. Docker Compose uses PostgreSQL; Kubernetes must
be configured with an externally managed PostgreSQL URL in
`AI_AGENT_CHAT_DATABASE`. The PostgreSQL adapter uses a bounded 20-connection
pool per application process. Do not share the SQLite file between replicas.

This is a scalable foundation, not a heavy-traffic service guarantee: the
current HTTP transport, per-IP rate limiter, and model inference path have not
been load-tested or distributed. Production rollout still needs load tests,
shared/distributed rate limiting, production identity/tenant provisioning,
provider capacity planning, and operational monitoring before public traffic.
See [deployment guidance](./22-deployment.md).

## Operator Frontend

The built-in dashboard is served at `/` and the React chat at `/chat/` on the
workflow API port.
Run the API server with:

```bash
python -m app.api.server_main
```

It includes a demo approval workflow, run controls, run details,
approval actions, cancellation, and Server-Sent Event output.

The chat frontend is built with Node, React, TypeScript, and Vite:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Run the Python API in another terminal. Vite proxies `/v1` requests to
`http://127.0.0.1:8081`. The production Docker image builds and packages the
static React assets automatically.

The UI supports bearer-token sign-in. Configure `AI_AGENT_ADMIN_TOKEN` and
`AI_AGENT_USER_TOKEN` to enable role-aware access. Administrators can create
workflows, approve/reject steps, and cancel runs. Users can run workflows and
inspect only their own runs. When no tokens are configured and the API binds to loopback, it enters
local-development mode with administrator access. The API entry point rejects
non-loopback binds unless authentication is explicitly required and at least
one token is configured; do not expose local-development mode to untrusted
networks.

REST-created workflow definitions, run snapshots, and hashed run ownership
persist through `ChatStore`. Approval-waiting runs recover after restart;
interrupted runs are marked failed instead of replayed. Python callable
workflows, live execution, event subscriptions, and cross-process worker
coordination remain in-process. The deployment PVC alone does not make these
services horizontally consistent.

Workflow definitions created through the UI use a restricted JSON schema. The
supported node types are `value`, `context`, and `join`; arbitrary code is
never accepted. Node count, retries, names, dependency graphs, and timeouts are
validated before registration.

For local development, start without tokens and the server grants local admin
access. For role-aware operation, provide separate admin and user tokens:

```powershell
$env:AI_AGENT_ADMIN_TOKEN = "replace-with-a-long-random-admin-token"
$env:AI_AGENT_USER_TOKEN = "replace-with-a-long-random-user-token"
$env:AI_AGENT_REQUIRE_AUTH = "true"
python -m app.api.server_main
```

Do not use example tokens or local-development mode on a public network.
