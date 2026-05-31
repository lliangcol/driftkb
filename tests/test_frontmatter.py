from __future__ import annotations

from pathlib import Path

import pytest

from driftkb.core.frontmatter import FrontmatterError, parse_markdown_frontmatter


def test_parse_markdown_frontmatter_returns_mapping_and_body(tmp_path: Path) -> None:
    kb_file = tmp_path / "payment.md"
    kb_file.write_text(
        """
---
last_verified_commit: abc123
source_globs:
  - "src/payment/**/*.py"
stale_policy: warn
anchor_symbols:
  - payment.PaymentService
adapters:
  - generic
owner: platform
tags:
  - payments
---
# Payment

Body text.
""".lstrip(),
        encoding="utf-8",
    )

    frontmatter, body = parse_markdown_frontmatter(kb_file)

    assert frontmatter["last_verified_commit"] == "abc123"
    assert frontmatter["source_globs"] == ["src/payment/**/*.py"]
    assert frontmatter["stale_policy"] == "warn"
    assert frontmatter["anchor_symbols"] == ["payment.PaymentService"]
    assert frontmatter["adapters"] == ["generic"]
    assert frontmatter["owner"] == "platform"
    assert frontmatter["tags"] == ["payments"]
    assert body.startswith("# Payment")


def test_parse_markdown_frontmatter_requires_frontmatter(tmp_path: Path) -> None:
    kb_file = tmp_path / "missing.md"
    kb_file.write_text("# Missing\n", encoding="utf-8")

    with pytest.raises(FrontmatterError, match="missing YAML frontmatter"):
        parse_markdown_frontmatter(kb_file)
