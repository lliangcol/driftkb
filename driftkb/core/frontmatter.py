from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from driftkb.core.config import ConfigError, parse_simple_yaml
from driftkb.core.models import ProfileConfig


class FrontmatterError(ValueError):
    """Raised when a Markdown KB file has missing or invalid frontmatter."""


@dataclass(frozen=True)
class FrontmatterDocument:
    frontmatter: dict[str, Any]
    body: str


def parse_markdown_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    markdown = path.read_text(encoding="utf-8")
    document = split_frontmatter(markdown)
    return document.frontmatter, document.body


def split_frontmatter(markdown: str) -> FrontmatterDocument:
    normalized = markdown.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        raise FrontmatterError("Markdown file is missing YAML frontmatter delimited by `---`.")

    end_marker = normalized.find("\n---\n", 4)
    if end_marker == -1:
        raise FrontmatterError("Markdown frontmatter is missing a closing `---` delimiter.")

    raw_frontmatter = normalized[4:end_marker]
    body = normalized[end_marker + len("\n---\n") :]

    try:
        frontmatter = parse_simple_yaml(raw_frontmatter)
    except ConfigError as exc:
        raise FrontmatterError(f"Invalid YAML frontmatter: {exc}") from exc

    if not frontmatter:
        raise FrontmatterError("Markdown frontmatter is empty.")

    return FrontmatterDocument(frontmatter=frontmatter, body=body)


def normalize_frontmatter_aliases(frontmatter: dict[str, Any], profile: ProfileConfig) -> dict[str, Any]:
    normalized = dict(frontmatter)
    for alias, canonical in profile.frontmatter_aliases.items():
        if alias not in normalized:
            continue
        if canonical in normalized:
            raise FrontmatterError(f"frontmatter cannot contain both {alias} and {canonical}.")
        normalized[canonical] = normalized[alias]
    return normalized
