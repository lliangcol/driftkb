# Call Graph Cache

DriftKB can use an optional static call graph cache to propagate review warnings from a directly stale KB page to related KB pages.

## Core Boundary

DriftKB core never calls MCP. DriftKB core only reads a static JSON cache from the configured `graph.cache_path`, which defaults to:

```text
.driftkb/call_graph_cache.json
```

The core validation path does not depend on Claude Code, codebase-memory-mcp, hosted services, graph databases, editor agents, or private code-intelligence tools.

## Schema

The cache schema is intentionally small:

```json
{
  "schema_version": 1,
  "nodes": {
    "payment.PaymentService": {
      "callers": [
        "api.PaymentController"
      ],
      "callees": [
        "payment.PaymentRepository"
      ]
    }
  }
}
```

Fields:

- `schema_version`: must be `1`.
- `nodes`: object keyed by symbol name.
- `callers`: symbols that call the keyed symbol.
- `callees`: symbols called by the keyed symbol.

If the cache is missing or invalid, `driftkb validate` continues without graph propagation and records WARN-level graph metadata in the JSON report.

## Frontmatter

Curated KB pages opt into propagation from their anchors:

```yaml
---
source_globs:
  - "src/payment/**/*.py"
anchor_symbols:
  - payment.PaymentService
propagate:
  callers: true
  callees: false
---
```

When a changed file directly makes this page stale, DriftKB reads `payment.PaymentService` from the cache. If `propagate.callers` is `true`, KB pages anchored to caller symbols are marked `WARN`. Propagation never produces `FAIL`.

## External Generators

Any graph provider can generate this file:

- MCP
- LSP
- CodeQL
- tree-sitter indexer
- custom script

The cache file should be committed or generated in CI before `driftkb validate` runs. Use `driftkb graph anchors` to print the curated KB `anchor_symbols` JSON array that an external generator can use as its input list.
