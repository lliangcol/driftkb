from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from driftkb.adapters.base import Fingerprint

SNAPSHOT_SCHEMA_VERSION = 1


def fingerprint_to_dict(fingerprint: Fingerprint) -> dict[str, Any]:
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "adapter": fingerprint.adapter,
        "file": fingerprint.file,
        "symbols": list(fingerprint.symbols),
        "annotations": list(fingerprint.annotations),
        "imports": list(fingerprint.imports),
        "raw_hash": fingerprint.raw_hash,
        "semantic_hash": fingerprint.semantic_hash,
        "metadata": _stable_value(fingerprint.metadata),
    }


def fingerprint_from_dict(data: dict[str, Any]) -> Fingerprint:
    return Fingerprint(
        adapter=str(data["adapter"]),
        file=str(data["file"]),
        symbols=tuple(str(item) for item in data.get("symbols", [])),
        annotations=tuple(str(item) for item in data.get("annotations", [])),
        imports=tuple(str(item) for item in data.get("imports", [])),
        raw_hash=data.get("raw_hash"),
        semantic_hash=data.get("semantic_hash"),
        metadata=dict(data.get("metadata", {})),
    )


def snapshot_path(snapshot_dir: Path, source_relative_path: str, adapter_name: str) -> Path:
    encoded = base64.urlsafe_b64encode(source_relative_path.encode("utf-8")).decode("ascii").rstrip("=")
    return snapshot_dir / adapter_name / f"{encoded}.json"


def load_snapshot(snapshot_dir: Path, source_relative_path: str, adapter_name: str) -> Fingerprint | None:
    path = snapshot_path(snapshot_dir, source_relative_path, adapter_name)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"fingerprint snapshot must contain a JSON object: {path}")
    return fingerprint_from_dict(data)


def save_snapshot(snapshot_dir: Path, fingerprint: Fingerprint) -> Path:
    path = snapshot_path(snapshot_dir, fingerprint.file, fingerprint.adapter)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fingerprint_to_dict(fingerprint), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def compare_fingerprint(current: Fingerprint, snapshot: Fingerprint | None) -> bool:
    if snapshot is None:
        return False
    if current.adapter != snapshot.adapter or current.file != snapshot.file:
        return False
    if current.semantic_hash is not None and snapshot.semantic_hash is not None:
        return current.semantic_hash == snapshot.semantic_hash
    return current.raw_hash is not None and current.raw_hash == snapshot.raw_hash


def _stable_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _stable_value(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [_stable_value(item) for item in value]
    if isinstance(value, list):
        return [_stable_value(item) for item in value]
    return value
