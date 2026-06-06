# Quickstart

This walkthrough uses the bundled minimal example to show the normal
`PASS -> FAIL` loop.

## Install

Install the published package:

```text
pipx install driftkb
uv tool install driftkb
```

For a source checkout:

```text
git clone https://github.com/lliangcol/driftkb.git
cd driftkb
python -m pip install -e ".[dev]"
```

## Run the Minimal Example

From the repository root:

```text
cd examples/minimal
driftkb validate
```

Expected output:

```text
DriftKB: PASS
```

The example KB page uses a fixed `last_verified_commit` SHA. DriftKB warns on
moving refs such as `HEAD` because they can hide drift after source commits.

## Create Drift

Edit `examples/minimal/src/payment.py`:

```python
PAYMENT_PROVIDER = "stripe"
```

Change the value to another provider and rerun:

```text
driftkb validate
```

Expected result: `FAIL`. The verify block in the KB page no longer matches the
source code.

## PowerShell Notes

On Windows PowerShell, quote extras when installing from source:

```text
python -m pip install -e ".[dev]"
```

Use the same CLI commands as other shells:

```text
driftkb version
driftkb validate --no-write-report --no-verify
driftkb gaps detect --dry-run
```

## Common Failures

- `last_verified_commit` is `HEAD` or a branch name: replace it with a fixed
  commit SHA, usually from `git rev-parse HEAD` after human review.
- `git` cannot find `HEAD`: commit the example checkout or run in a normal clone.
- `rg` is missing: install ripgrep before running verify blocks.
- Validation writes a report you do not want: pass `--no-write-report`.
- Reviewing untrusted changes: pass `--no-verify` to skip verify block execution.

## Next Steps

- Run `driftkb init` in your own repository.
- Add curated KB pages under `docs/kb/curated/`.
- Declare `source_globs`, `last_verified_commit`, and `stale_policy` in
  frontmatter.
- Add constrained `rg` verify blocks for mechanical assertions.
- Install a hook with `driftkb hooks install pre-push` when the checks are stable.
