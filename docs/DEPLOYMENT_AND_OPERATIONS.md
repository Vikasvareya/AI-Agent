# Deployment and Operations

## Supported examples

The repository includes a local Python service, Dockerfile, Docker Compose
configuration, and Kubernetes examples. These examples do not establish an
SLO, high availability, production security, or heavy-traffic capacity.
Kubernetes expects external PostgreSQL and Ollama services. REST workflow
definitions and run snapshots use `ChatStore`, but execution, event delivery,
and rate limiting are not coordinated across API instances.

## Local service

Install Python dependencies and start the API:

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-chat.txt
python -m app.api.server_main
```

Defaults are API port `8081` and health port `8080`. The API bind address and
ports are environment-configurable. The service needs a reachable Ollama
instance; chat persistence uses SQLite by default unless PostgreSQL is
configured. See [API and Developer Guide](./API_AND_DEVELOPER_GUIDE.md).

The API entry point allows unauthenticated development only on a loopback
bind. A non-loopback bind requires `AI_AGENT_REQUIRE_AUTH=true` and at least
one configured API/admin/user token; invalid boolean configuration fails
startup. Use [.env.example](../.env.example) as a key-only template and never
put real secrets in that example.

## Docker Compose

Compose builds the frontend and runs the API, PostgreSQL, and Ollama services.
Supply unique credentials and database configuration through a secret manager
or deployment environment; never copy live secrets into a checked-in file.
Ollama models are not automatically downloaded. Chat, coding, and workflow UI
routes are served by the API on port `8081`; health is on port `8080`.

The coding workspace remains disabled unless `AI_AGENT_CODING_WORKSPACE`
points to an intended workspace. Mount only authorized project data, and
remember that selected files can be sent to the configured model provider.

## Kubernetes

The manifests are illustrative. Configure external PostgreSQL, Ollama
connectivity, secret delivery, image registry access, ingress/TLS, storage,
and cluster-specific policy before applying them. Review all manifest values
without copying secret contents into docs or source control.

The manifests do not by themselves make the application horizontally
consistent. Workflow definitions and run snapshots can use shared PostgreSQL,
But live workflow execution has no distributed worker/lease boundary.
Coding proposals and permission mode persist in `ChatStore`, but permission
updates are not synchronized across live replicas. Rate limits and event
subscriptions remain process-local. A configured replica count or HPA is not proof that these
stateful behaviors work across replicas. The checked-in PVC is not a
substitute for shared PostgreSQL and is not mounted as a shared database for
this state.

## Health and operations

The health service exposes liveness/readiness routes and `/metrics`. The
current metrics response is a static up gauge; it is not application-level
telemetry or an alerting integration. Confirm the exact checks in
`app/health/` before using them as deployment gates.

Before production use, define:

- TLS termination, trusted proxy headers, secure-cookie settings, CORS, and
  ingress limits.
- Secret creation, rotation, revocation, and incident response.
- PostgreSQL backup/restore, migration, retention, and access policy.
- Model-server capacity, timeouts, concurrency, and provider failure behavior.
- Logs/metrics/traces, alert thresholds, SLOs, and an on-call owner.
- Rollback procedures and tested recovery from API, database, and model
  outages.

## Verification status

The project has previously passed its Python test suite and frontend
production build, but this documentation update does not validate container
images or deploy the Kubernetes examples. See
[Testing and Quality](./TESTING_AND_QUALITY.md) for verification commands and
known gaps.
