# DriftKB Roadmap

## v0.1: Validation Foundation

Goal: ship the first usable local and CI validation loop.

Status: implemented in the `0.1.0` MVP release.

Scope:

- `driftkb validate` command.
- Markdown KB discovery under configurable KB roots, defaulting to `docs/kb/`.
- Frontmatter parsing for validation metadata.
- X5 verify-block execution.
- Stale-policy checks using git diff and configured source globs.
- Minimal fingerprint checks.
- Optional static call graph cache reader.
- JSON report output.
- Pre-push hook template that calls `driftkb validate`.
- README and docs safety notes for repository-local command execution.

## v0.2: Gap Detection Workflow

Goal: identify missing KB coverage without making generated output trusted by default.

Status: partially implemented in `0.1.0`; future work should refine reports,
workflow docs, and risk-pattern tuning.

Scope:

- `driftkb gaps detect` command.
- Configurable source discovery for modules and features that should have KB coverage.
- Generated stub output for missing coverage candidates.
- Promote workflow that requires human review before generated material becomes curated KB.
- JSON gap report output.
- Documentation that gap detection is a manual command and is not part of the default pre-push gate.

## v0.3: Adapter Plugin API

Goal: make language-specific fingerprinting extensible.

Planned scope:

- Stable adapter interface for fingerprint extraction.
- Built-in generic adapter.
- Java regex adapter refinement.
- Preview adapters for Python, TypeScript, and Go.
- Adapter configuration examples.
- Tests that prove the core does not hard-code any single language.

## v0.4: Graph Provider Plugin

Goal: define an optional provider boundary for call graph cache generation.

Planned scope:

- Graph provider plugin interface.
- Cache schema for generated call graph data.
- Validation that core can consume the static cache without provider dependencies.
- Example external generator integration.
- Documentation for provider security and portability expectations.

## v1.0: Stable Open Source Baseline

Goal: stabilize the public contract for production repository use.

Planned scope:

- Stable configuration schema.
- Stable JSON report schema.
- Stable verify-block format.
- Stable adapter API.
- CI examples for common providers.
- Hook installation docs.
- Complete user documentation.
- Migration notes for pre-1.0 users.
