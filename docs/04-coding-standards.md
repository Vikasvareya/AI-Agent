# Coding and Documentation Standards

Follow existing Python, TypeScript, and React conventions. Keep changes
focused, preserve type information, and add tests for behavior or safety
boundaries that change. The repository does not currently establish a
mandatory formatter or linter configuration; do not imply that one runs in
CI.

Before submitting, run the focused pytest tests, the frontend build when UI
code changes, and `git diff --check`. Report checks that could not be run.
Never commit secrets, private data, generated caches, or build output.

Documentation must distinguish verified implementation from proposals,
include operational constraints, and link to the authoritative guides in the
repository README.
