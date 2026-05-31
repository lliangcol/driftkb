# Concepts

DriftKB focuses on keeping curated Markdown knowledge bases aligned with the code they describe.

## Drift

Drift means an existing curated KB page no longer matches the codebase. A service may be renamed, a contract may change, an assumption may stop being true, or a referenced symbol may disappear.

DriftKB is planned to detect drift through frontmatter, git diff, fingerprints, verify blocks, and optional graph cache signals.

## Gap

Gap means new or changed code lacks curated KB coverage. Gap detection is advisory and manual by default:

```text
driftkb gaps detect
```

Generated gap output is not trusted KB. A human must review and curate it before it belongs under `docs/kb/`.

## Curated

Curated KB files are human-reviewed Markdown files, normally under `docs/kb/`. DriftKB treats curated files as the source of documentation truth, then validates whether their declared evidence still holds.

## Generated

Generated output may come from scanners, gap detection, graph exporters, or future optional tools. Generated output can help humans find missing docs, but it must not be automatically promoted into curated KB.

`driftkb promote` is the manual promotion path for reviewed generated stubs. It
moves a stub from `docs/kb/generated/` to `docs/kb/curated/` and rewrites only
promotion metadata such as `kind`, `last_verified_commit`, and `stale_policy`.
The command requires `validation_status: human_reviewed` and `reviewed_by`; it
does not create trusted business content.

## Verify blocks

Verify blocks are executable assertions embedded in Markdown. They are planned to run during `driftkb validate` and should be treated as repository code because they execute commands.

## Fingerprint

A fingerprint is a lightweight semantic summary of source files. Early adapters are planned to include a generic adapter and a Java regex adapter, with other languages added later.

Fingerprints are not intended to replace compilers, test suites, or full static analyzers.

## Graph cache

A graph cache is an optional static JSON file that describes relationships such as symbol or file dependencies. DriftKB core only reads this file. It does not call MCP, graph databases, editor agents, or private tools directly.
