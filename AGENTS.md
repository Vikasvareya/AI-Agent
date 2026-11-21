# Development Agent Instructions

This file applies to coding agents working on this repository. It is separate
from runtime system prompts in `app/agents/` and `app/chat/service.py`.

## Objective

Preserve existing behavior while aligning code and documentation with the
[AI Brain Master Architecture](docs/AI_BRAIN_MASTER_ARCHITECTURE.md). Prefer
surgical, backward-compatible changes.

## Mandatory rules

1. Inspect source, tests, and documentation before changing behavior.
2. Distinguish IMPLEMENTED, PARTIAL, PROTOTYPE, PLANNED, NOT IMPLEMENTED, and
   EXPERIMENTAL capabilities in documentation.
3. Do not claim model training, autonomous tool creation, robotics, distributed
   agent collaboration, or conscious/autonomous intelligence unless source and
   tests verify it.
4. Preserve the loopback-first API, static-auth compatibility, coding
   workspace boundaries, and explicit patch approval behavior.
5. Do not execute generated code, shell commands, or plugins inside the API
   process. Isolated workers and resource limits are required for execution.
6. Keep secrets out of source, logs, fixtures, prompts, screenshots, and
   commits. Rotate exposed credentials separately.
7. Add focused tests for authorization, file boundaries, persistence,
   validation, and failure behavior when application code changes.
8. Run the smallest relevant validation first, then the full suite if the
   change warrants it. Report actual test/build results.
9. Update [Implementation Status](docs/IMPLEMENTATION_STATUS.md),
   [Current Implementation](docs/CURRENT_IMPLEMENTATION.md),
   [Known Limitations](docs/KNOWN_LIMITATIONS.md), and the relevant architecture
   guide when behavior changes.
10. Do not commit, deploy, or rewrite Git history unless the user explicitly
   requests it.

## Validation

PowerShell:

```powershell
python -m pytest -q
git diff --check
Set-Location frontend
npm run build
```
