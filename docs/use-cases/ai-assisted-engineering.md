# Use Case: AI-Assisted Engineering

AI coding assistants often read repository Markdown as durable context. That is
useful only when the Markdown still reflects the code.

## Problem

A team documents architecture decisions, integration assumptions, and business
rules in Markdown. Code changes later rename an entry point, change a provider,
or add a new high-risk module. The KB page still looks authoritative, so humans
and AI assistants continue using stale context.

## DriftKB Workflow

1. Curated KB pages declare `source_globs`, `last_verified_commit`, and
   `stale_policy` in frontmatter.
2. Verify blocks capture mechanical assertions such as symbols, routes, or
   configuration values that should still exist.
3. `driftkb validate` compares the current repo with the declared KB evidence.
4. Hooks or CI fail or warn before stale context spreads.
5. `driftkb gaps detect` can be run manually to find high-risk uncovered areas.
6. Generated stubs remain untrusted until a human reviews and promotes them.

## Recommended Gate

Use `driftkb validate` in pre-push or PR CI once the KB pages are stable. Keep
`driftkb gaps detect` manual until the project has tuned its risk patterns.

For untrusted pull requests, run:

```text
driftkb validate --no-verify
```

This keeps stale/frontmatter checks available while skipping verify block
execution.
