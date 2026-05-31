# DriftKB Project Brief

## Positioning

DriftKB is an open source Python CLI that keeps Markdown knowledge bases honest. It warns or fails when code changes make knowledge-base pages stale, unverifiable, or missing.

DriftKB is designed for repositories that keep architecture notes, business rules, integration contracts, operational assumptions, and similar engineering knowledge in Markdown. Its job is to make those pages checkable during local development and CI without turning the documentation system into a hosted service or an AI authoring workflow.

## Target Users

The primary users are engineering teams using AI-assisted development. These teams rely on Markdown knowledge bases as durable project memory, but need automated checks when code changes invalidate existing documentation or introduce new code areas that lack curated knowledge-base coverage.

## Core Problems

### Drift

Drift happens when an existing Markdown KB page no longer matches the codebase. Examples include a documented entry point being renamed, a source file referenced by the page being removed, or a verify block assertion no longer passing.

DriftKB should detect drift through configured source globs, stale policies, fingerprints, verify blocks, git diff context, and optional call graph cache propagation.

### Gap

Gap happens when new modules or features are added without corresponding KB coverage. Gap detection is advisory in the MVP-era workflow and is not part of the default pre-push gate.

Generated gap output may help authors draft missing coverage, but generated content is not trusted KB. Promotion from generated output to curated KB must require human review.

## Core Components

### K / Validate Orchestrator

K is the validation orchestrator. It reads Markdown KB frontmatter, combines it with git diff information, `source_globs`, `stale_policy`, verify blocks, fingerprints, and optional call graph cache data, then emits a `PASS`, `WARN`, or `FAIL` result.

K also writes a machine-readable JSON report so local tooling, CI jobs, and hooks can consume the same validation result.

### X5 / Verify Blocks

X5 is the verify-block mechanism embedded in Markdown KB pages. A verify block contains a mechanical assertion that DriftKB can execute during validation, such as a search command that confirms a symbol, route, file, or contract still exists.

Because verify blocks execute repository-local commands, DriftKB must document their safety implications clearly. The CLI should capture command errors and present understandable validation output.

Verify blocks provide mechanical verification only. They do not prove the full business meaning or correctness of the KB prose.

### J / Fingerprint

J is the lightweight semantic fingerprint layer. It extracts stable source fingerprints that can reveal meaningful code changes without requiring full static analysis.

The MVP should include a generic fingerprint mechanism and a Java regex adapter as the first example adapter. Java is not special in the core design; language adapters must be configurable and replaceable.

### F / Call Graph Cache

F is the optional call graph cache reader. DriftKB core reads a static `call_graph_cache.json` file and uses it for warning propagation when a changed node may affect documented behavior elsewhere.

The core must not directly depend on MCP, private tools, editor agents, or a graph database. Any future graph integration must generate or provide a static cache through a separate optional plugin or external generator.

## MVP Scope

The MVP includes:

- K validate orchestration for Markdown KB pages.
- X5 verify blocks.
- Minimal J fingerprint support with generic extraction and a Java regex adapter.
- Optional F static call graph cache reader.
- JSON validation report output.
- A pre-push hook that calls the generic CLI command `driftkb validate`.
- Conservative local and CI workflows for open source repositories.

## Explicitly Out Of Scope

The MVP does not include:

- SaaS, hosted validation, or remote services.
- Databases or background workers.
- AI-generated automatic edits to curated KB pages.
- Full multi-language static analysis.
- A complete graph provider system.
- Mandatory MCP, editor-agent, or private-tool integration.
- Default pre-push gap detection.

## MCP And Graph Dependency Principle

DriftKB core must not depend on MCP. The core reads only static repository files, including an optional `call_graph_cache.json`.

MCP, graph databases, editor agents, or other code-intelligence systems may be future optional providers, but they must sit outside the core validation path and must produce portable cache files or reports that DriftKB can read without those systems being installed.

## Default Paths

Default KB root:

```text
docs/kb/
```

Curated and generated files live under:

```text
docs/kb/curated/
docs/kb/generated/
```

Default configuration directory:

```text
.driftkb/
```

Both paths must be configurable.

## Distribution

DriftKB is distributed as a Python 3.10+ CLI package.

Package name:

```text
driftkb
```

CLI command:

```text
driftkb
```

Primary distribution channel:

```text
PyPI
```

Recommended installation methods:

```text
pipx install driftkb
uv tool install driftkb
```

## License

DriftKB uses the Apache-2.0 license.
