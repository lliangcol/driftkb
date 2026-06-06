from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

GRAPH_PROVIDER_ENTRY_POINT_GROUP = "driftkb.graph_providers"


class GraphProvider(Protocol):
    name: str

    def generate(self, repo_root: Path, output_path: Path, options: dict[str, Any]) -> Path:
        """Generate a DriftKB call graph cache and return the written path."""
