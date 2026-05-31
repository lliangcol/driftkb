from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class Fingerprint:
    adapter: str
    file: str
    symbols: tuple[str, ...] = ()
    annotations: tuple[str, ...] = ()
    imports: tuple[str, ...] = ()
    raw_hash: str | None = None
    semantic_hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class FingerprintAdapter(Protocol):
    name: str

    def supports(self, path: Path) -> bool:
        """Return whether this adapter can extract a fingerprint for path."""

    def extract(self, path: Path, source_root: Path) -> Fingerprint:
        """Extract a deterministic lightweight fingerprint from a source file."""
