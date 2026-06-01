# Contributing

DriftKB is an early-stage Python CLI project. Contributions should keep the core portable, local-first, and free of private project assumptions.

## Development setup

Use Python 3.10 or newer. From the repository root:

```text
python -m pip install -e ".[dev]"
```

## Running tests

Run tests:

```text
python -m pytest
```

Run the local quality checks used by CI:

```text
ruff check .
ruff format --check .
python -m pytest --cov=driftkb --cov-report=term-missing
python -m build
```

For CLI smoke checks during early development:

```text
python -m driftkb version
python -m driftkb init
python -m driftkb validate
```

## Pull requests

Please include:

- what changed and why;
- tests or smoke checks run;
- docs updates for user-facing behavior;
- safety notes if verify execution, hooks, or generated KB promotion changed.

PRs should not add private paths, private repository names, or organization-specific
assumptions. Public examples should use portable paths such as `docs/kb/` and
`.driftkb/`.

## Submitting adapters

Adapters should extract lightweight source fingerprints without making the core depend on a single language, framework, or repository layout.

When proposing an adapter:

- Keep the adapter optional and explicitly selected by configuration.
- Document what source facts it extracts and what it intentionally ignores.
- Include tests for representative source snippets.
- Provide clear fallback behavior when files cannot be parsed.
- Avoid heavyweight runtime dependencies unless there is a strong reason.

## Project boundaries

- Do not add hosted service requirements to the core package.
- Do not make the core directly depend on MCP, editor agents, graph databases, or private tooling.
- Do not hard-code private paths, private repository names, or organization-specific layouts.
- Do not hard-code one language. Java is only an early example adapter.
- Do not auto-promote generated gap output into trusted curated KB files.
- Treat verify blocks as executable project code and document safety implications.

Examples and tests should use portable paths such as `docs/kb/` and `.driftkb/`.
