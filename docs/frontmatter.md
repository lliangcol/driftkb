# Frontmatter

DriftKB reads YAML frontmatter from curated Markdown KB files to understand what each page claims to cover. Frontmatter must be repository-portable: do not use machine-local absolute paths or private repository names.

Example:

```yaml
---
last_verified_commit: abc123
source_globs:
  - "src/payment/**/*.py"
stale_policy: warn
anchor_symbols:
  - payment.PaymentService
propagate:
  callers: true
  callees: false
adapters:
  - generic
---
```

## Fields

## `last_verified_commit`

The commit at which the KB page was last manually reviewed against the source it describes.

## `source_globs`

Repository-relative glob patterns for source files covered by the KB page.

## `stale_policy`

How DriftKB should react when covered source evidence changes after `last_verified_commit`.

Allowed values:

- `warn`: report stale evidence without failing validation.
- `fail`: fail validation when stale evidence is detected.
- `skip`: do not apply stale-source checks for this page.

## `anchor_symbols`

Important modules, classes, functions, routes, jobs, commands, or other named anchors that the KB depends on.

## `propagate`

Optional call graph propagation settings for this page's `anchor_symbols`.

- `callers`: when `true`, warn KB pages anchored to symbols that call this page's anchors.
- `callees`: when `true`, warn KB pages anchored to symbols called by this page's anchors.

Propagation depends on the static call graph cache and only emits `WARN`.

## `adapters`

Fingerprint adapters to use for this page. Adapter names are configuration values. The core does not assume Java, MCP, or any other specific language or graph provider.

## `owner`

Optional human or team owner for review routing.

## `tags`

Optional labels for grouping reports, ownership, or manual review workflows.
