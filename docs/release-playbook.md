# Release Playbook

This playbook captures repository settings and external steps that cannot be
fully represented in tracked files.

## Repository Settings

Set the GitHub About description to:

```text
Catch stale Markdown knowledge-base docs when code changes.
```

Add these GitHub topics:

```text
documentation-drift
docs-as-code
knowledge-base
markdown-validation
developer-tools
python-cli
ci
devex
ai-engineering
static-analysis
```

Upload `assets/social-preview.png` as the GitHub social preview image.

Create or confirm these issue labels:

```text
bug
feature
question
good first issue
help wanted
docs
examples
tests
validation
verify-blocks
fingerprints
gaps
adapters
hooks
reporting
packaging
ci
security
release
design
graph
python
```

## PyPI Trusted Publishing

Before pushing `v0.1.0`, configure a pending trusted publisher on PyPI:

```text
PyPI project: driftkb
Owner: lliangcol
Repository: driftkb
Workflow: release.yml
Environment: pypi
```

If the PyPI project name is not available, stop the release and choose a new
public package name intentionally. Do not publish under a fallback name without
updating docs, metadata, and install instructions.

## First Release

1. Confirm the local release checklist passes.
2. Push the release commit.
3. Push tag `v0.1.0`.
4. Wait for the Release workflow to build, publish to PyPI, and create the
   GitHub release.
5. Run post-publish smoke checks:

```text
pipx install driftkb
uv tool install driftkb
driftkb version
driftkb validate --no-write-report --no-verify
```

## Launch Copy

English:

```text
I built DriftKB, a local Python CLI for catching stale Markdown knowledge-base
docs when code changes. It validates curated KB pages using git diff,
frontmatter, constrained verify blocks, fingerprints, and JSON reports for
hooks and CI.
```

Chinese:

```text
我做了一个开源 CLI：DriftKB。它解决的是代码变化后 Markdown 知识库悄悄过期的问题，尤其适合 AI 辅助开发场景。
```
