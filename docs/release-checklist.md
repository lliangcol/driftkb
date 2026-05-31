# Release Checklist

Use this checklist for each PyPI release.

## Prepare

- Confirm the working tree only contains intended release changes.
- Bump the version in `driftkb/__init__.py`.
- Bump the version in `pyproject.toml`.
- Update `CHANGELOG.md`.
- Review `README.md` for claims that exceed implemented behavior.
- Review security notes for verify blocks and repository-local command execution.

## Validate

```text
pytest
driftkb --help
driftkb version
driftkb validate --no-write-report
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

## Publish TestPyPI

```text
python -m twine upload --repository testpypi dist/*
pipx install --index-url https://test.pypi.org/simple/ --pip-args "--extra-index-url https://pypi.org/simple/" driftkb
driftkb version
```

## Publish PyPI

```text
python -m twine upload dist/*
pipx install driftkb
driftkb version
```

## GitHub Release

- Create and push a version tag, for example `v0.1.0`.
- Create a GitHub release from the tag.
- Attach release notes from `CHANGELOG.md`.
- Confirm the GitHub release links to the PyPI package.
