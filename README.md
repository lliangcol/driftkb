# DriftKB

DriftKB keeps Markdown knowledge bases honest by warning or failing when code changes make them stale, unverifiable, or missing.

## Problem

AI-assisted engineering teams often keep architecture notes, business rules, integration contracts, and operational assumptions in Markdown knowledge bases. Those files become part of the working context for humans and AI assistants.

After code changes, several things can go wrong:

- KB pages drift away from the code they describe.
- New modules or features may ship with a KB gap.
- An AI assistant may read stale docs and give wrong advice.
- Code review may miss documentation drift, especially when the changed code and affected KB page are far apart.

## Solution

DriftKB validates curated Markdown KB files against the codebase.

Validation produces one of three statuses:

- `PASS`: the KB appears current for the configured checks.
- `WARN`: DriftKB found stale or incomplete evidence that should be reviewed.
- `FAIL`: a configured policy or verify block failed.

## How it works

DriftKB is planned as a local Python CLI that combines:

1. Markdown frontmatter that declares what each curated KB page covers.
2. Git diff information to identify changed source areas.
3. Fingerprint adapters that extract lightweight source facts.
4. An optional static graph cache for warning propagation.
5. Verify blocks embedded in KB Markdown.
6. A JSON report that CI, hooks, and humans can inspect.

## Quickstart

Install from PyPI when published:

```text
pipx install driftkb
uv tool install driftkb
```

Try the bundled minimal example from a source checkout:

```text
cd examples/minimal
driftkb validate
```

This expects a normal git checkout with a valid `HEAD` commit, because the
example KB uses `last_verified_commit: HEAD`. The first run should print
`DriftKB: PASS`. Now edit `src/payment.py` and change
`PAYMENT_PROVIDER = "stripe"` to another value:

```text
driftkb validate
```

The second run reports `FAIL` because the KB assertion no longer matches the
code.

Initialize the default project layout:

```text
driftkb init
```

This creates the default configuration directory and KB root:

```text
.driftkb/config.yml
docs/kb/curated/
docs/kb/generated/
```

Initialize the Enterprise Java-compatible profile layout without hard-coding a local
checkout path:

```text
driftkb init --profile enterprise-java
```

This writes a sample `.driftkb/config.yml` only if it does not already exist and
creates `.agents/kb/zh/curated/`, `.agents/kb/zh/generated/`, and validation
directories. The profile enables Enterprise Java-compatible paths, `anchor_classes`
frontmatter aliases, and the `enterprise-java` adapter through config/profile only.

Validate curated KB files:

```text
driftkb validate
driftkb validate --profile enterprise-java
```

By default this scans `docs/kb/curated/**/*.md`, compares each page's
`source_globs` with files changed since `last_verified_commit` including
uncommitted worktree changes, prints a text summary, and writes
`.driftkb/validation/last-run.json`.

Update fingerprint snapshots explicitly:

```text
driftkb fingerprints update --all
```

Validation can use matching snapshots in `.driftkb/validation/fingerprints/` to
avoid reporting a changed file as stale when its current fingerprint is already
trusted. Validation never updates snapshots automatically.

Install a pre-push hook that calls the generic CLI:

```text
driftkb hooks install pre-push
```

Existing `.git/hooks/pre-push` files are not overwritten unless you pass
`--force`. Use `--strict` if the hook should fail on `WARN` as well as `FAIL`.

Run advisory gap detection manually:

```text
driftkb gaps detect
driftkb gaps detect --profile enterprise-java
```

Gap detection is not part of the default pre-push gate.

Gap detection only reports high-risk candidates by default. Configure
project-specific `gaps.risk_patterns` when you want adapters such as the Java
regex adapter to flag framework annotations.

Promote a human-reviewed generated stub into curated KB:

```text
driftkb promote docs/kb/generated/payment-service-stub.md
driftkb promote .agents/kb/zh/generated/payment-service-stub.md --profile enterprise-java
```

Promotion only moves an existing generated stub after human review. Before
promotion, the stub must have `validation_status: human_reviewed` and a
non-empty `reviewed_by` field. The command updates frontmatter for curated
validation and does not generate business content or trust AI draft text
automatically.

With `--profile enterprise-java`, generated stubs use
`review_status: pending_review` and `anchor_classes`. Promotion accepts
`review_status: reviewed` plus a non-empty `reviewer` field, then normalizes the
file for curated validation.

## Example KB frontmatter

```yaml
---
title: Checkout flow
last_verified_commit: 8f3c2a1
source_globs:
  - src/checkout/**
  - tests/checkout/**
stale_policy: warn
anchor_symbols:
  - CheckoutService
  - create_order
adapters:
  - generic
  - java-regex
---
```

## Verify block example

````markdown
```bash verify
rg "class CheckoutService|def create_order" src/checkout tests/checkout
# expected: match_count >= 1
```
````

MVP verify blocks only execute `rg` commands. Non-`rg` commands are reported as
`WARN` unless verify execution is disabled.

## Configuration

Project configuration lives in `.driftkb/config.yml` by default. The schema is early and planned to cover:

- KB roots such as `docs/kb/`.
- Source include and exclude globs.
- Adapter selection and fingerprint snapshot location.
- Verify block execution limits.
- Optional call graph cache location.
- Report output options.

All paths, adapters, and graph providers should be configurable. The core must not assume a particular repository layout or programming language.

See `docs/profiles.md` for profile-specific config defaults and compatibility
fields.

## Security note

Verify blocks execute commands from repository Markdown files. Treat them like scripts or tests:

- Do not run DriftKB validation in an untrusted repository.
- Review `.driftkb/config.yml` and KB verify blocks before enabling them in CI.
- The MVP only executes constrained `rg` verify commands; shell execution is not implemented.
- Verify commands cannot use `rg` preprocessors, symlink-following flags, absolute paths, or parent-directory traversal.
- Keep CI credentials scoped so a malicious verify block cannot access unnecessary secrets.
- Disable verify blocks in CI with `driftkb validate --no-verify` when reviewing untrusted changes.

## Status

DriftKB is early-stage. The current MVP includes config loading, curated KB frontmatter scanning, git-diff based stale checks, `rg` verify blocks, fingerprint snapshots, optional call graph cache warning propagation, advisory gap detection, generated stub promotion, text output, JSON reports, and pre-push hook installation.

## License

Apache-2.0.
