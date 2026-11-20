# Testing

The canonical test commands and quality expectations are in
[TESTING_AND_QUALITY.md](./TESTING_AND_QUALITY.md).

Tests are grouped by subsystem under `tests/`. Use `python -m pytest -q` for
the backend suite, and run `npm ci` followed by `npm run build` in `frontend`
for frontend compilation. Add focused regression cases for behavior,
authorization, input boundaries, and failure handling.

The current backend validation recorded 144 passing Python tests and a
successful frontend build. GitHub Actions now runs those checks on pushes and
pull requests; it does not yet test container builds, deployment manifests,
or production behavior.
