# Adapters

Adapters extract lightweight fingerprints from source files. Their job is to provide useful evidence without making DriftKB a heavyweight static analysis framework.

## Design goals

- Keep the core language-neutral.
- Make adapters explicitly configurable.
- Keep dependencies small.
- Prefer predictable, testable extraction over complex inference.
- Return useful partial results when a file cannot be fully parsed.
- Preserve clear errors for unsupported files or broken encodings.

## MVP adapters

The MVP includes:

- `generic`: computes a deterministic SHA-256 hash for any supported text or binary file.
- `java` / `java-regex`: a minimal Java-oriented regex adapter.

The Java adapter is an example adapter, not a core assumption. Future adapters may cover Python, Go, TypeScript, or other ecosystems.

## What adapters may extract

Adapters may report facts such as:

- File paths and content hashes.
- Classes, functions, methods, or modules.
- Routes, commands, jobs, or config keys when they are easy to identify.
- References to anchor symbols declared in frontmatter.

## What adapters should avoid

Adapters should not:

- Require private tooling.
- Call MCP, editor agents, graph databases, or hosted services from the core validation path.
- Depend on machine-local absolute paths.
- Claim full semantic correctness unless they actually provide it.

Unknown adapter names are configuration errors. DriftKB fails fast instead of
falling back to another adapter, so typos do not silently reduce coverage.

## Generic adapter

The generic adapter supports any file path that exists as a regular file. It records:

- repo-relative file path from the configured source root
- raw SHA-256 hash
- semantic hash equal to the raw hash

This adapter is intentionally conservative. Whitespace-only changes still change the fingerprint.

## Java regex adapter preview

The Java adapter supports `.java` files and uses regular expressions, not a Java AST. It records:

- package declaration
- class, interface, and enum names
- fully qualified class names when a package is present
- imports
- annotations as raw text, including common forms such as `@Transactional`, `@DS`, `@XxlJob`, and `@RocketMQMessageListener`
- public and protected method names

Limitations:

- It does not resolve constants, annotation aliases, inherited types, overload semantics, or imports.
- It can miss unusual formatting, nested declarations, comments that look like code, and complex generic signatures.
- It should be treated as preview evidence for reducing obvious false positives, not as semantic proof.

## Snapshots

Fingerprint snapshots are stored as deterministic JSON under `.driftkb/validation/fingerprints/` by default. The location is configurable:

```yaml
fingerprints:
  enabled: true
  snapshot_dir: .driftkb/validation/fingerprints
```

Update snapshots explicitly:

```text
driftkb fingerprints update --all
driftkb fingerprints update --kb-file docs/kb/curated/example.md
```

`driftkb validate` never updates snapshots automatically. If a changed source file has no snapshot, or extraction fails, DriftKB remains conservative and reports the stale match.

Fingerprints reduce false positives. They are not a complete semantic proof that a KB page is correct.
