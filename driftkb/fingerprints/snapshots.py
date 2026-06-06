from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from driftkb.adapters.base import Fingerprint

SNAPSHOT_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class FingerprintSnapshot:
    fingerprint: Fingerprint
    generated_at_commit: str | None = None
    kb_path: str | None = None
    kb_last_verified_commit: str | None = None
    source_changed_since_kb_last_verified: bool | None = None


def fingerprint_to_dict(
    fingerprint: Fingerprint,
    *,
    generated_at_commit: str | None = None,
    kb_path: str | None = None,
    kb_last_verified_commit: str | None = None,
    source_changed_since_kb_last_verified: bool | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
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
    if generated_at_commit is not None:
        payload["generated_at_commit"] = generated_at_commit
    if kb_path is not None:
        payload["kb_path"] = kb_path
    if kb_last_verified_commit is not None:
        payload["kb_last_verified_commit"] = kb_last_verified_commit
    if source_changed_since_kb_last_verified is not None:
        payload["source_changed_since_kb_last_verified"] = source_changed_since_kb_last_verified
    return payload


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
    snapshot = load_snapshot_record(snapshot_dir, source_relative_path, adapter_name)
    return snapshot.fingerprint if snapshot is not None else None


def load_snapshot_record(
    snapshot_dir: Path,
    source_relative_path: str,
    adapter_name: str,
) -> FingerprintSnapshot | None:
    path = snapshot_path(snapshot_dir, source_relative_path, adapter_name)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"fingerprint snapshot must contain a JSON object: {path}")
    source_changed = data.get("source_changed_since_kb_last_verified")
    if source_changed is not None and not isinstance(source_changed, bool):
        raise ValueError(f"fingerprint snapshot source_changed_since_kb_last_verified must be boolean: {path}")
    return FingerprintSnapshot(
        fingerprint=fingerprint_from_dict(data),
        generated_at_commit=_optional_string(data, "generated_at_commit"),
        kb_path=_optional_string(data, "kb_path"),
        kb_last_verified_commit=_optional_string(data, "kb_last_verified_commit"),
        source_changed_since_kb_last_verified=source_changed,
    )


def save_snapshot(
    snapshot_dir: Path,
    fingerprint: Fingerprint,
    *,
    generated_at_commit: str | None = None,
    kb_path: str | None = None,
    kb_last_verified_commit: str | None = None,
    source_changed_since_kb_last_verified: bool | None = None,
) -> Path:
    path = snapshot_path(snapshot_dir, fingerprint.file, fingerprint.adapter)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            fingerprint_to_dict(
                fingerprint,
                generated_at_commit=generated_at_commit,
                kb_path=kb_path,
                kb_last_verified_commit=kb_last_verified_commit,
                source_changed_since_kb_last_verified=source_changed_since_kb_last_verified,
            ),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
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


def _optional_string(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"fingerprint snapshot field `{key}` must be a string")
    return value
