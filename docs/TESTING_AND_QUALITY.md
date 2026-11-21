# Testing and Quality

## Test layout

The repository uses pytest with tests grouped by subsystem: agents, API,
context, executor, health, MCP, memory, observability, planner, plugins,
providers, realtime, and workflows. Frontend code is built with the scripts in
`frontend/package.json`.

## Local checks

From the repository root:

```powershell
python -m pytest -q
```

For frontend verification:

```powershell
Set-Location frontend
npm ci
npm run build
```

Return to the repository root after frontend commands. The backend tests can
be run by subsystem, for example `python -m pytest tests/api -q`.

## Quality expectations

- Add focused regression tests for new behavior and safety boundaries.
- Test unauthorized, malformed, stale, and boundary-sized inputs—not just
  successful responses.
- Use temporary directories/databases for filesystem and persistence tests.
- Stub external providers in unit tests; do not require live credentials.
- Keep secrets out of test fixtures, logs, screenshots, and generated reports.
- Test restart/recovery and multi-process behavior before claiming durable or
  horizontally consistent execution.
- Treat frontend build success as compilation evidence, not full UI or
  accessibility validation.
- Executor changes require dependency-validation, fail-fast lifecycle,
  typed argument-resolution, re-execution, and legacy-agent retry coverage.

## Current evidence and gaps

The backend suite is measured per run and should be reported from the actual
completed command. GitHub Actions runs the backend suite,
frontend production build, full-history Gitleaks scan, Compose configuration
validation, application container build/startup smoke test, and Kubernetes
manifest schema validation on pushes and pull requests. The scanners are
version-pinned and verify release archive checksums before execution.

Kubernetes deployment, model-inference smoke testing, load/soak/chaos tests,
tenant-isolation assurance, dependency vulnerability scanning, and live Brave
Search integration have not been established by the available test evidence.

Use [Implementation Status](./IMPLEMENTATION_STATUS.md) and
[Product Roadmap](./PRODUCT_ROADMAP.md) to track these gaps.
