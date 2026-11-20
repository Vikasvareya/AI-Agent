# Security

The authoritative security posture, threat boundaries, and required
remediation are maintained in
[SECURITY_AND_GOVERNANCE.md](./SECURITY_AND_GOVERNANCE.md).

Do not expose local-development authentication mode to untrusted networks.
Use approved secret storage, keep private source authorized before sending it
to a model provider, treat shared-session links as bearer credentials, and
never enable untrusted code or plugin execution in the API process.

The tracked `.env` was removed from the Git index in the current worktree;
the local copy was preserved and is ignored. Its contents were not read or
reproduced. Review repository history and rotate potentially exposed values,
because untracking does not erase prior commits.
