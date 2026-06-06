# DriftKB

[![CI](https://github.com/lliangcol/driftkb/actions/workflows/ci.yml/badge.svg)](https://github.com/lliangcol/driftkb/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/driftkb.svg)](https://pypi.org/project/driftkb/)
[![Python](https://img.shields.io/pypi/pyversions/driftkb.svg)](https://pypi.org/project/driftkb/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

Catch stale Markdown knowledge-base docs when code changes.

DriftKB is an early-stage local Python CLI for validating curated Markdown
knowledge bases against the code they describe. It is built for teams that use
Markdown as durable engineering memory, especially in AI-assisted development
workflows where stale repo docs can mislead both humans and assistants.

![DriftKB terminal demo](https://raw.githubusercontent.com/lliangcol/driftkb/main/assets/demo-terminal.svg)

## Why

Architecture notes, business rules, integration contracts, and operational
assumptions often live in Markdown. Code changes faster than those pages do.
DriftKB turns that drift into a local or CI signal before stale docs become
trusted context.

DriftKB validates curated KB pages using:

- frontmatter that declares covered source paths and policies;
- git diff context, including staged, unstaged, and untracked source changes;
- constrained `rg` verify blocks embedded in Markdown;
- lightweight source fingerprints bound to the KB review baseline;
- optional static call graph cache propagation;
- text and JSON reports for hooks, CI, and humans.

Validation returns:

- `PASS`: configured checks currently pass.
- `WARN`: DriftKB found stale or incomplete evidence that should be reviewed.
- `FAIL`: a policy, frontmatter rule, or verify block failed.

## Install

Install the published package:

```text
pipx install driftkb
uv tool install driftkb
```

If the PyPI release is not available yet, install from a source checkout:

```text
git clone https://github.com/lliangcol/driftkb.git
cd driftkb
python -m pip install -e ".[dev]"
```

## Quickstart

Run the bundled minimal example:

```text
cd examples/minimal
driftkb validate
```

Expected output:

```text
DriftKB: PASS
```

Now edit `src/payment.py` and change:

```python
PAYMENT_PROVIDER = "stripe"
```

to another value, then run:

```text
driftkb validate
```

Expected result: `FAIL`, because the KB assertion no longer matches the code.

See [docs/quickstart.md](docs/quickstart.md) for the full walkthrough.

## Core Commands

Initialize a project:

```text
driftkb init
```

This creates:

```text
.driftkb/config.yml
docs/kb/curated/
docs/kb/generated/
```

Validate curated KB files:

```text
driftkb validate
driftkb validate --format json
driftkb validate --strict
```

Update fingerprint snapshots explicitly:

```text
driftkb fingerprints update --all
driftkb fingerprints update --all --accept-current
```

Use `--accept-current` only after human review. It updates selected curated KB
files to the current `HEAD` and writes snapshots tied to that baseline.

Install a pre-push or pre-commit hook:

```text
driftkb hooks install pre-push
driftkb hooks install pre-commit --strict --no-verify
```

The default hook calls the generic CLI command `driftkb validate`. Gap detection
is not part of the default pre-push gate.

Run advisory gap detection manually:

```text
driftkb gaps detect
```

Promote a human-reviewed generated stub into curated KB:

```text
driftkb promote docs/kb/generated/payment-service-stub.md
```

Promotion only moves existing generated stubs after human review. DriftKB does
not generate business content or automatically trust AI-written drafts.

## Enterprise Java-Compatible Profile

DriftKB includes an optional `enterprise-java` profile for repositories that use
a `.agents/kb/zh/` layout:

```text
driftkb init --profile enterprise-java
driftkb validate --profile enterprise-java
driftkb gaps detect --profile enterprise-java
```

The profile enables compatible paths, `anchor_classes` frontmatter aliases, and
the `enterprise-java` adapter through config/profile only. The core is not
locked to Java or to that layout.

## Verify Block Example

````markdown
```bash verify
rg "class CheckoutService|def create_order" src/checkout tests/checkout
# expected: match_count >= 1
```
````

MVP verify blocks only execute constrained `rg` commands. Non-`rg` commands are
reported as `WARN` unless verify execution is disabled. `rg` commands must use
explicit path operands relative to the source root. Use
`driftkb validate --verify-debug-samples` when you need bounded stdout/stderr
samples in the JSON report while debugging a failing block.

## Configuration

Project configuration lives in `.driftkb/config.yml` by default. Paths,
adapters, reports, fingerprints, and optional graph cache locations are
configurable. The core does not depend on MCP, editor agents, hosted services,
graph databases, or a particular programming language.

Useful docs:

- [Quickstart](docs/quickstart.md)
- [Concepts](docs/concepts.md)
- [Comparison](docs/comparison.md)
- [Frontmatter](docs/frontmatter.md)
- [Verify blocks](docs/verify-blocks.md)
- [Gap detection](docs/gap-detection.md)
- [Profiles](docs/profiles.md)
- [Call graph cache](docs/call-graph-cache.md)
- [CI](docs/ci.md)
- [Roadmap](docs/roadmap.md)

## Security

Verify blocks execute commands from repository Markdown files. Treat them like
scripts or tests:

- Run DriftKB only in repositories you trust.
- Review `.driftkb/config.yml` and KB verify blocks before enabling CI.
- Keep CI credentials scoped to least privilege.
- Disable verify blocks with `driftkb validate --no-verify` when reviewing
  untrusted changes.

See [SECURITY.md](SECURITY.md) for details.

## Status

Current features include config loading, curated KB frontmatter scanning,
git-diff stale checks, constrained `rg` verify blocks, baseline-bound
fingerprint snapshots, built-in generic/Java/Python adapters, adapter plugin
entry points, optional static call graph cache warning propagation, advisory gap
detection, generated stub promotion, JSON reports, and pre-push/pre-commit hook
installation.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Good first contribution areas include
docs, examples, adapter tests, CI/packaging hardening, and reproduction cases.

## License

Apache-2.0.
