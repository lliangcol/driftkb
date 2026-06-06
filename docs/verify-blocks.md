# Verify Blocks

Verify blocks are executable assertions embedded in curated Markdown KB pages.
They run during `driftkb validate` unless verification is disabled.

## Format

Use a fenced code block whose info string contains `verify`:

````markdown
```bash verify
# Expected symbol still exists.
rg -n "class PaymentService" src tests
# expected: match_count >= 1
```
````

Supported MVP info strings include:

- `bash verify`
- `sh verify`
- `verify`

DriftKB also recognizes legacy-style markers that contain `verify`, but new KB
pages should use the forms above.

## Expected Syntax

The MVP assertion syntax is intentionally small:

```text
# expected: match_count >= N
```

`N` must be a non-negative integer. DriftKB counts non-empty stdout lines from
`rg` as `match_count`.

## Command Support

The MVP only executes commands whose first token is `rg`.

Return code handling:

- `0`: matches were found; non-empty stdout lines become `match_count`.
- `1`: no matches; `match_count` is `0`.
- `2` or any other code: the verify block becomes `WARN`, not `FAIL`.
- missing `rg`: the verify block becomes `WARN` with an installation message.

If `match_count` does not satisfy the expected value, the verify block becomes
`FAIL` and `driftkb validate` exits with code `1`.

Non-`rg` commands are reported as `WARN`. Arbitrary shell execution is not
implemented in the MVP.

Every verify block must include an expected assertion. A block without
`# expected: match_count >= N` is reported as `WARN` instead of passing by
default.

For safety, DriftKB runs `rg` with config loading disabled, rejects `rg`
preprocessors, rejects symlink-following flags, and requires explicit path
operands to stay inside the configured source root.

Good:

```text
rg -n "PaymentService" src/payment tests/payment
```

Rejected because it would scan the whole source root:

```text
rg -n "PaymentService"
```

Use forward slashes in examples for portability. Windows-style relative
operands are accepted, but POSIX-style paths are easier to review across
platforms.

## Safety

Verify blocks execute commands from repository Markdown files. Treat them like
scripts or tests:

- Do not run verify blocks in untrusted repositories.
- Review KB changes before enabling verify blocks in CI.
- Prefer read-only, deterministic commands.
- Avoid commands that mutate files, require network access, or depend on broad
  secrets.
- Do not use absolute paths or parent-directory path traversal in verify
  commands.
- Keep CI credentials scoped and short-lived.

## CI

Run validation with verify blocks enabled:

```text
driftkb validate
```

Disable verify blocks for untrusted changes or early rollout:

```text
driftkb validate --no-verify
```

Tune the per-command timeout:

```text
driftkb validate --verify-timeout 5
```

When debugging a failing verify block, include bounded stdout/stderr samples in
the text and JSON report:

```text
driftkb validate --verify-debug-samples
```
