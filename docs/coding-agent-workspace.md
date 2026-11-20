# Coding Agent Workspace

The coding workspace is a separate administrator-facing application at
`/chat/coding/`. It shares the React/Vite bundle and API deployment with chat, but
has its own workspace-first navigation and task flow.

## Current workflow

The coding workspace opens in a conversation-first dark layout. The sidebar
contains project folders and saved sessions; the composer keeps project,
session, model, task type, selected-file context, and permission mode together.
Use **Workspace** to open the existing file editor and patch-review workbench,
and **Settings** to review permissions, models, projects, conversations, and
integration availability. **Customizations** reports the current integration
status; it does not install or invoke tools. Automations and marketplace
installation are not configured capabilities.

1. Configure `AI_AGENT_CODING_WORKSPACE` to an existing project directory.
2. Sign in as an administrator. The workspace root and each eligible direct
   child folder appear as projects. In **Settings > Projects**, create a
   project inside a selected parent directory or add an existing project from
   the server's file system. The location picker can browse drives and folders;
   the selected external project is registered in the chat database so it
   remains available after restart.
3. Create or reopen a project session. Sessions are persisted in the configured
   chat database and keep their prompts and proposals across reloads/restarts.
   The latest 12 saved messages, capped at 16,000 characters, are supplied as
   untrusted context for follow-up tasks.
4. Open an eligible file in the editor or create a file in an existing
   selected-project directory. Saving is an explicit administrator action and checks
   that an opened file has not changed since it was loaded. The HTML preview
   runs in a sandbox with scripts and external network resources blocked;
   other file types use a text preview.
5. Select up to eight eligible files, choose an installed model, and describe
   a feature, bug fix, refactor, test task, or DSA problem. Review the generated
   unified diff. The API validates file paths, hunk counts, and old lines
   against the selected source.
6. In manual mode, apply or reject the agent's pending proposal. Applying
   checks that source files have not changed since generation.

The editor can create files only in existing directories. Creating project
folders at the workspace root is supported. Administrators can permanently
delete a configured-workspace child folder and its saved conversations after
confirmation; the workspace root cannot be deleted. Removing an
externally-selected project only removes its workspace link and saved
conversations; the project files remain untouched. Conversations can also be
deleted individually, which removes their messages and invalidates their share
links.
Individual file deletion, rename, nested directory creation, command execution,
and automatic plugin/MCP invocation are not supported.

## Permission modes

| Action | Manual (default) | Auto |
| --- | --- | --- |
| Read selected eligible files | Allowed | Allowed |
| Generate a scoped patch | Allowed | Allowed |
| Write a validated patch | Requires an explicit Apply action | Applied immediately after validation |
| Save editor content | Requires an explicit Save action | Requires an explicit Save action |
| Execute shell commands | Disabled | Disabled |
| Invoke plugins or MCP tools | Disabled | Disabled |

Auto mode requires an explicit confirmation through the administrator API and
is limited to the selected project directory. The server persists permission
mode, owner-scoped pending proposals, and hashed-actor audit events in the
configured `ChatStore`. Permission mode, including confirmed auto mode,
survives restart.
Pending proposals can be applied after restart if the workspace identity is
unchanged; a proposal interrupted during application is invalidated and must
be generated again. Standalone `CodingAgent` instances without a store remain
process-local.

All coding routes require administrator authorization. Configure
`AI_AGENT_ADMIN_TOKEN` and `AI_AGENT_REQUIRE_AUTH=true` before exposing the API.
Never expose local-development mode or mount a workspace the administrator is
not authorized to share with the configured model provider.

The API entry point rejects non-loopback binds unless authentication is
explicitly required and at least one API/admin/user token is configured.
Authentication boolean settings must be valid true/false values.

### Sessions and sharing

Coding sessions are scoped to the administrator identity and project. The
database stores at most the latest 100 session messages; prompt context uses a
smaller, bounded recent window. A session can be shared only after an explicit
confirmation. The resulting read-only link contains a random bearer token,
expires after seven days, and can be invalidated with **Revoke shares**. Anyone
who receives the link can read the session prompts and proposals, so do not
share sessions containing secrets or private code.

The SQLite database is suitable for local/single-instance use; PostgreSQL is
the durable option for a deployment. Administrative sessions are keyed to the
configured administrator credential identity; rotating that identity starts a
separate session history.

### Editor and project boundaries

Projects can be direct folders under `AI_AGENT_CODING_WORKSPACE` or
administrator-selected external directories. The directory browser and project
management APIs are administrator-only and operate on the server's file system.
For container deployments, mount the selected host directories into the API
container first.
The editor reads and writes only allowlisted text formats inside the selected
project directory, enforces the 32 KiB file limit, and uses an explicit Save
action with stale-file checks. HTML preview is
sandboxed and blocks scripts and remote resources. Editor saves are direct
user actions; agent-generated patches still follow the separate manual/auto
permission mode.

## Skills, plugins, MCP, and models

The dashboard reports current integration availability instead of claiming
that unsupported integrations are connected:

- The framework has plugin and MCP building blocks, but the coding agent does
  not currently invoke them.
- A skill registry and skill execution policy are not implemented.
- Installed models can be listed and selected through the configured provider.
- Dataset management, model training/fine-tuning jobs, evaluation, and model
  deployment are not implemented. The dashboard identifies this gap; it does
  not simulate training.

The task type selector includes DSA problems, but solution quality depends on
the selected model and generated patches still require validation and review.
The framework does not currently provide a DSA-specific execution sandbox.

## API and implementation boundaries

The API is documented in [19-api.md](./19-api.md). The workspace is enabled by
`AI_AGENT_CODING_WORKSPACE`; generation timeout is controlled by
`AI_AGENT_CODING_TIMEOUT`. Coding proposals have bounded file counts and
context and exclude common secret and generated paths. The API stores pending
proposal patches and originals in the configured chat database, so protect
that database as source-code data. `GET /v1/coding/proposals` lists the
authenticated owner's pending proposals after a restart. Coding session
metadata and messages use the same store.

The current service is a local/single-instance foundation, not a proven
high-traffic coding platform. Permission changes are not synchronized across
live replicas; audit coverage beyond coding actions, distributed job
orchestration, quota/rate controls, immutable artifact storage, and load/chaos
tests remain future work. Coding audit events are available through a paginated
admin API and are pruned after 365 days by default; set
`AI_AGENT_CODING_AUDIT_RETENTION_DAYS=0` to retain them indefinitely.
Multi-file writes use staged temporary files with rollback attempts, but
cross-filesystem transactions are not guaranteed.

## Planned platform milestones

1. Extend proposal ownership to an explicit tenant model and add audit coverage
   for privileged actions beyond the coding workspace.
2. Add isolated worktree/container execution with resource/network controls
   and per-command approvals; do not run untrusted code in the API process.
3. Add a reviewed skill registry, signed plugin manifests, and an MCP server
   registry with per-tool scopes, timeouts, audit, and human approval.
4. Add background task queues, streaming progress, cancellation, resumable
   runs, and horizontal worker scaling.
5. Add model lifecycle services: import, training-data governance, fine-tuning
   jobs, evaluation gates, versioning, rollout, and rollback.

These are roadmap items, not current dashboard capabilities. Any future
automatic tools must remain workspace/tenant scoped and separately authorized.
