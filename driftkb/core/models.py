from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ValidationStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True)
class KBFile:
    path: Path
    frontmatter: dict[str, Any]
    body: str
    last_verified_commit: str | None = None
    source_globs: tuple[str, ...] = ()
    stale_policy: str = "warn"
    anchor_symbols: tuple[str, ...] = ()
    propagate_callers: bool = False
    propagate_callees: bool = False
    adapters: tuple[str, ...] = ()
    owner: str | None = None
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    path: Path | None = None
    severity: ValidationStatus = ValidationStatus.WARN
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VerifyBlock:
    name: str | None
    language: str
    command: str
    expected: str | None = None
    path: Path | None = None


@dataclass(frozen=True)
class Fingerprint:
    adapter: str
    path: Path
    symbol: str
    digest: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphCache:
    path: Path
    schema_version: int = 1
    nodes: tuple[str, ...] = ()
    edges: tuple[tuple[str, str], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationResult:
    result: ValidationStatus
    checked_at_commit: str | None = None
    stale: tuple[ValidationIssue, ...] = ()
    warnings: tuple[ValidationIssue, ...] = ()
    verify: tuple[ValidationIssue, ...] = ()
    gaps: tuple[ValidationIssue, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


# Backwards-compatible aliases for the initial skeleton.
KnowledgeBasePage = KBFile
ValidationReport = ValidationResult
