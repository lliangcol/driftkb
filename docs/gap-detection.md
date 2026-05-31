# Gap Detection

Gap detection identifies high-risk source symbols that may lack curated KB coverage. It is advisory and manual by default.

Run it explicitly:

```bash
driftkb gaps detect
```

The default mode is a dry run. It prints gaps but does not modify the repository:

```bash
driftkb gaps detect --dry-run
```

Write generated stubs only when you explicitly ask for them:

```bash
driftkb gaps detect --write
```

Use JSON output for scripts:

```bash
driftkb gaps detect --format json
```

## Not a default pre-push gate

Gap detection is not planned to run in the default pre-push hook. The hook should call the generic validation command:

```bash
driftkb validate
```

This keeps local pushes focused on stale or failing curated KB checks. Gap detection can be noisier because it may identify new modules, renamed areas, or generated code that needs human judgment.

## Generated versus curated

Gap detection output is generated evidence, not trusted documentation. Generated files are written under `docs/kb/generated/` by default and use frontmatter such as:

```yaml
kind: generated
validation_status: pending_human_review
generator: driftkb gaps detect
```

Generated suggestions must not be automatically promoted to trusted KB. A maintainer should review them, write or update curated Markdown, and commit the result under `docs/kb/curated/`.

After human review, mark the stub as reviewed by changing the generated
frontmatter to include a human reviewer:

```yaml
validation_status: human_reviewed
reviewed_by: alice@example.com
```

Then move the reviewed generated stub into curated KB with:

```bash
driftkb promote docs/kb/generated/example-stub.md
```

`promote` checks `kind: generated`, requires `validation_status:
human_reviewed`, requires `reviewed_by`, does not call AI, does not generate
business content, refuses to overwrite an existing curated file, and refuses to
run when git has staged changes. Use `--dry-run` to inspect the planned move
first. Use `--update-fingerprints` only after the human review has established
that the promoted KB and its source evidence are current. When
`--update-fingerprints` is used, covered source files must be clean in the
working tree so snapshots stay tied to the recorded `last_verified_commit`.
Use `--config` when promotion should read a non-default DriftKB config file.

## Configuration

Gap detection uses the configured source globs and enabled adapters:

```yaml
sources:
  root: .
  include:
    - "src/**/*"
  exclude:
    - "**/.git/**"
adapters:
  enabled:
    - generic
    - java
gaps:
  enabled: true
  whitelist_path: .driftkb/gap_whitelist.txt
  # Keep this list project-specific. These Java annotations are examples, not
  # DriftKB core defaults.
  risk_patterns:
    - "@Transactional"
    - "@RocketMQMessageListener"
    - "@XxlJob"
    - "@DS"
```

The MVP treats a candidate as high risk when an enabled adapter extracts an annotation matching `risk_patterns`. The default list is empty so new projects can choose their own risk signals. The Java regex adapter is the first example adapter; the core command does not require Java and does not depend on MCP or private graph tools.

## Whitelist

`.driftkb/gap_whitelist.txt` supports exact symbols, glob patterns, blank lines, and comments:

```text
# Covered by external operational docs.
com.example.LegacyJob
com.example.generated.*
```

Whitelisted candidates are omitted from generated stubs and counted as `skipped_whitelisted`.

## Review workflow

1. Run `driftkb gaps detect`.
2. Review candidates and whitelist intentional exceptions.
3. Run `driftkb gaps detect --write` for stubs that need human follow-up.
4. Manually write or update the generated stub until it is suitable curated KB.
5. Set `validation_status: human_reviewed` and `reviewed_by`.
6. Run `driftkb promote docs/kb/generated/<stub>.md`.
7. Run `driftkb validate`.
