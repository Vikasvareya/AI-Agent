# Development Workflow

1. Read [Current Implementation](./CURRENT_IMPLEMENTATION.md) and
   [Known Limitations](./KNOWN_LIMITATIONS.md) before extending a subsystem.
2. Keep the change scoped and follow the existing module boundaries.
3. Add focused tests, including negative and boundary cases where relevant.
4. Run `python -m pytest -q`; for UI changes, run `npm ci` and `npm run build`
   from `frontend`.
5. Run `git diff --check` and inspect the final diff for unrelated files,
   secrets, caches, and unsupported claims.
6. Update the relevant module guide and authoritative status/roadmap docs.

GitHub Actions now runs the backend suite and frontend build on pushes and pull
requests. Run the same checks locally before submitting; the workflow does not
replace review of secrets, deployment manifests, or security-sensitive changes.
See [Contributing](./CONTRIBUTING.md) for setup and submission expectations.
