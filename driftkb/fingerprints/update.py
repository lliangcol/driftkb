from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from driftkb.adapters.registry import build_adapters
from driftkb.core.config import DriftKBConfig
from driftkb.core.paths import path_matches_any
from driftkb.core.validate import all_source_files, load_kb_file, scan_curated_kb_files
from driftkb.fingerprints.snapshots import save_snapshot


@dataclass(frozen=True)
class FingerprintUpdateResult:
    updated: int
    skipped: int


def update_fingerprints(
    config: DriftKBConfig,
    *,
    kb_file: Path | None = None,
    all_kb: bool = False,
) -> FingerprintUpdateResult:
    kb_paths = _selected_kb_paths(config, kb_file=kb_file, all_kb=all_kb)
    source_paths = all_source_files(config)
    updated = 0
    skipped = 0
    seen: set[tuple[str, str]] = set()

    for kb_path in kb_paths:
        page = load_kb_file(kb_path, config)
        adapters = build_adapters(page.adapters or config.adapters.enabled)
        for source_path in source_paths:
            if not path_matches_any(source_path, page.source_globs):
                continue
            absolute = config.sources.root / source_path
            adapter = next((item for item in adapters if item.supports(absolute)), None)
            if adapter is None:
                skipped += 1
                continue
            fingerprint = adapter.extract(absolute, config.sources.root)
            key = (fingerprint.adapter, fingerprint.file)
            if key in seen:
                continue
            save_snapshot(config.fingerprints.snapshot_dir, fingerprint)
            seen.add(key)
            updated += 1

    return FingerprintUpdateResult(updated=updated, skipped=skipped)


def _selected_kb_paths(config: DriftKBConfig, *, kb_file: Path | None, all_kb: bool) -> tuple[Path, ...]:
    if kb_file is not None:
        path = kb_file if kb_file.is_absolute() else config.repo_root / kb_file
        return (path.resolve(),)
    if all_kb:
        return scan_curated_kb_files(config.kb.curated_dir)
    return ()
