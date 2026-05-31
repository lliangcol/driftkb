from __future__ import annotations

import hashlib
from pathlib import Path

from driftkb.adapters.base import Fingerprint


class GenericAdapter:
    name = "generic"

    def supports(self, path: Path) -> bool:
        return path.is_file()

    def extract(self, path: Path, source_root: Path) -> Fingerprint:
        source = path.read_bytes()
        relative = path.resolve().relative_to(source_root.resolve()).as_posix()
        digest = hashlib.sha256(source).hexdigest()
        return Fingerprint(
            adapter=self.name,
            file=relative,
            raw_hash=digest,
            semantic_hash=digest,
        )
