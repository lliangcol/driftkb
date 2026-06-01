# Release Checklist

Use this checklist for each PyPI release.

## Prepare

- Confirm the working tree only contains intended release changes.
- Bump the version in `driftkb/__init__.py`.
- Bump the version in `pyproject.toml`.
- Update `CHANGELOG.md`.
- Review `README.md` for claims that exceed implemented behavior.
- Review security notes for verify blocks and repository-local command execution.
- Confirm PyPI has a pending trusted publisher for `lliangcol/driftkb`.
- Confirm the PyPI project name `driftkb` is available before creating a tag.

## Validate

```text
ruff check .
ruff format --check .
pytest
pytest --cov=driftkb --cov-report=term-missing
driftkb --help
driftkb version
driftkb validate --no-write-report --no-verify
driftkb gaps detect --dry-run
driftkb graph anchors
```

Run a hook smoke test in a temporary git repository:

```text
driftkb init
driftkb validate
driftkb gaps detect --dry-run
driftkb graph anchors
driftkb hooks install pre-push
```

## Build

```text
python -m build
python -m twine check dist/*
```

## Publish

Publishing should use the GitHub Actions `Release` workflow and PyPI Trusted
Publishing. Do not manually upload release artifacts unless the workflow is
unavailable and the maintainer has reviewed the fallback.

For the first release:

- Configure PyPI Trusted Publishing for owner `lliangcol`, repository
  `driftkb`, workflow `release.yml`, environment `pypi`.
- Create and push a version tag, for example `v0.1.0`.
- Confirm the release workflow publishes to PyPI.

## Post-Publish Smoke

```text
pipx install driftkb
uv tool install driftkb
driftkb version
driftkb validate --no-write-report --no-verify
```

## GitHub Release

- Create a GitHub release from the tag if the workflow did not create one.
- Attach release notes from `CHANGELOG.md`.
- Confirm the GitHub release links to the PyPI package.
- Confirm README badges resolve after the PyPI package is visible.
