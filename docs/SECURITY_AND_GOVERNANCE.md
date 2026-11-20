# Security and Governance

## Scope and status

This is a security posture summary, not a penetration-test report or
certification. The current service uses static bearer tokens and has
process-local controls. Do not expose it to untrusted networks without an
independently reviewed deployment and identity boundary.

## Current controls

- API authorization distinguishes configured admin and user tokens; chat
  conversations are scoped to the authenticated subject.
- Coding routes require admin authorization and a configured workspace root.
  File selection, path containment, extension exclusions, file size, and
  context size are bounded.
- Generated patches are checked against selected files and source context.
  Manual review is the default; explicit auto-apply remains workspace-scoped.
- Editor writes require explicit save and check stale source content.
- Coding session shares are opt-in, read-only, revocable, expire after seven
  days, and store a hash of the share token.
- Web search is opt-in per message and submits separate search terms rather
  than the chat prompt. Search results remain untrusted input.
- Health and API ports can be configured independently.

## Material limitations and audit findings

- **Environment-file remediation:** `.env` was removed from the Git index in
  the current worktree, the local file was preserved, and `.env`/`.env.*` are
  now ignored except for `.env.example`. The file contents were not read or
  reproduced. The index change does not erase prior commits: review repository
  access/history and rotate potentially exposed values.
- Local-development mode may grant admin access when authentication is not
  required and no tokens are configured. The API entry point now rejects
  non-loopback binds unless authentication is required and at least one token
  is configured. Never expose local-development mode publicly.
- Tokens are static configuration, not a managed identity, session-revocation,
  or full RBAC system. Multiple replicas need consistent identity mapping.
- Rate limiting is process-local and not resistant to distributed abuse.
- The server persists owner-scoped pending coding proposals, permission mode,
  and proposal/permission audit events in `ChatStore`; owner and actor values
  are digests, not bearer tokens. Interrupted applies are invalidated on
  restart. Audit retention and a read/export API are not implemented, and
  permission changes are not synchronized across live replicas.
- Plugins import Python code in-process. No plugin sandbox or signature
  verification exists. MCP is not connected to the coding agent.
- The API does not provide a code-execution sandbox. Do not add shell or
  untrusted code execution inside the API process.
- Shared session URLs are bearer credentials. Anyone with a valid link can
  read its content until expiry or revocation.
- Files and prompts selected for coding may be sent to the configured model
  provider. Users must be authorized to disclose that data to that provider.
- Kubernetes examples include a Secret manifest template and external service
  assumptions. Supply credentials through a secret manager; do not copy
  secret values into documentation or source control.

## Threat boundaries

Treat user input, model output, selected source files, prior conversation
history, and web-search results as untrusted. Validate at the server boundary.
UI-only restrictions do not constitute authorization. Keep model/provider
credentials server-side and prevent secrets from entering prompts, logs,
fixtures, screenshots, and reports.

## Required controls before production exposure

1. Remove tracked secrets and rotate affected credentials; add secret scanning
   to local and hosted workflows. Verify the staged `.env` deletion before
   committing this change. Review prior commits separately because the index
   removal does not rewrite Git history.
2. Require secure authentication for deployed environments and define token
   rotation, revocation, and recovery.
3. Extend durable authorization/audit coverage to all privileged actions and
   define audit retention/export controls; coding proposals already use
   digest-scoped ownership and durable action records.
4. Add cross-replica coordination for proposal decisions and permission
   updates; move distributed rate limiting, workflow execution coordination,
   and event delivery to appropriate shared services before horizontal
   scaling. Workflow and coding records already use `ChatStore`, but runtime
   coordination remains process-local.
5. Validate TLS/proxy configuration, secure cookies, CORS/origin policy,
   request limits, database access, and backup encryption.
6. Threat-model extensions and any future execution workers; default deny,
   least privilege, timeouts, resource caps, and revocation are mandatory.
7. Test authorization, path traversal, stale writes, share expiry/revocation,
   prompt injection, dependency failures, and recovery.

See [Known Limitations](./KNOWN_LIMITATIONS.md) and
[Deployment and Operations](./DEPLOYMENT_AND_OPERATIONS.md).
