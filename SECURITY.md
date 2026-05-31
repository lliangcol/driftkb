# Security

DriftKB is a local CLI. Verify blocks are planned to execute repository commands during validation, so they must be reviewed with the same care as scripts, tests, hooks, and CI jobs.

## Verify block risks

A malicious or careless verify block could:

- Attempt to read local files available to the current user.
- Attempt to exfiltrate secrets through network-capable commands.
- Attempt to modify the working tree.
- Run slow or resource-intensive commands.
- Produce misleading validation output.

The MVP only executes constrained `rg` commands. DriftKB disables ripgrep config
loading, rejects preprocessors, rejects symlink-following flags, and requires
explicit path operands to stay inside the configured source root.

Only run DriftKB in repositories you trust. Before enabling validation in CI, review `.driftkb/config.yml`, files under `docs/kb/`, and any hook configuration that invokes `driftkb validate`.

## Reporting Issues

Please report vulnerabilities through the repository's private security advisory process when available. If that is not available yet, open a minimal public issue that does not disclose exploit details and ask for a private contact path.

## Recommended use

- Run DriftKB only in trusted repositories.
- Keep CI credentials scoped to the least privilege needed.
- Review verify blocks before accepting KB changes.
- Treat generated gap output as untrusted until a human curates it into `docs/kb/`.
- Avoid running validation with elevated operating system privileges.

The current project is early-stage. Security-sensitive behaviors should remain explicit in README and docs as they are implemented.
