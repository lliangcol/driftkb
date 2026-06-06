# CI

Run DriftKB in CI after checkout and Python installation:

```yaml
name: DriftKB

on:
  pull_request:
  push:

jobs:
  driftkb:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install driftkb
      - run: driftkb validate --strict
```

Use `fetch-depth: 0` when your KB baselines may point to commits outside the
default shallow checkout. For early rollout or untrusted changes, use:

```text
driftkb validate --no-verify --format json
```

Pre-commit users can install the bundled hook:

```yaml
repos:
  - repo: https://github.com/lliangcol/driftkb
    rev: v0.1.0
    hooks:
      - id: driftkb-validate
```

Repository-local hooks are available too:

```text
driftkb hooks install pre-push --strict
driftkb hooks install pre-commit --no-verify
```
