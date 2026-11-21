# Contributing

Thanks for helping improve the framework. Keep changes scoped, documented,
tested, and explicit about whether a capability is implemented or proposed.

Development work is guided by the repository-level
[AGENTS.md](../AGENTS.md), the
[AI Brain Master Architecture](./AI_BRAIN_MASTER_ARCHITECTURE.md), and the
[Shared Agent Constitution](./AGENT_CONSTITUTION.md).

## Development setup

PowerShell from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -r requirements-chat.txt
python -m pytest -q
```

For frontend work:

```powershell
Set-Location frontend
npm ci
npm run build
```

The API starts with `python -m app.api.server_main`; the older CLI starts with
`python main.py`. See [API and Developer Guide](./API_AND_DEVELOPER_GUIDE.md).

## Change expectations

- Preserve existing layering and reuse repository helpers.
- Add focused tests for changed behavior, especially authorization, input
  validation, filesystem boundaries, persistence, and failure cases.
- Keep secrets, private source, real user data, and credentials out of commits,
  tests, logs, screenshots, and documentation.
- Do not claim production readiness, provider portability, durable execution,
  or ARES support without the required implementation and evidence.
- Update the relevant topic guide and authoritative status/roadmap docs when
  behavior or support level changes.
- Keep dependencies minimal and describe security/operational consequences.

## Before submitting

```powershell
python -m pytest -q
git diff --check
```

For frontend changes, run `npm run build` from `frontend`. If a test cannot be
run, state why and report the remaining validation gap. Do not include
generated caches, build output, databases, or secret files.

## Documentation

Use the authoritative files linked from the repository README. Existing
numbered guides remain useful for module detail, but must not contradict
current implementation status. Use Mermaid only for diagrams that match
verified code. Proposed designs must be clearly labeled as proposed.

GitHub Actions runs the backend suite and frontend build on pushes and pull
requests. Report local validation performed with the change; the workflow does
not yet run secret scanning, container deployment, or load tests.
