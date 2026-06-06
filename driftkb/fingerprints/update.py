from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from driftkb.adapters.registry import build_adapters
from driftkb.core.config import DriftKBConfig, dump_simple_yaml
from driftkb.core.frontmatter import parse_markdown_frontmatter
from driftkb.core.git import GitError, commit_exists, get_changed_files, get_head_commit, is_fixed_commit_ref
from driftkb.core.paths import path_matches_any, repo_paths_relative_to_source_root
from driftkb.core.validate import all_source_files, load_kb_file, scan_curated_kb_files
from driftkb.fingerprints.snapshots import save_snapshot


@dataclass(frozen=True)
class FingerprintUpdateResult:
    updated: int
    skipped: int
    accepted: int = 0


def update_fingerprints(
    config: DriftKBConfig,
    *,
    kb_file: Path | None = None,
    all_kb: bool = False,
    accept_current: bool = False,
) -> FingerprintUpdateResult:
    kb_paths = _selected_kb_paths(config, kb_file=kb_file, all_kb=all_kb)
    source_paths = all_source_files(config)
    updated = 0
    skipped = 0
    accepted = 0
    seen: set[tuple[str, str]] = set()
    try:
        head_commit = get_head_commit(config.repo_root)
    except GitError as exc:
        raise ValueError(str(exc)) from exc

    for kb_path in kb_paths:
        if accept_current:
            _ensure_covered_sources_clean_at_head(config, kb_path, head_commit)
            _write_last_verified_commit(kb_path, head_commit)
            accepted += 1
        page = load_kb_file(kb_path, config)
        adapters = build_adapters(page.adapters or config.adapters.enabled)
        changed_since_baseline = _changed_since_kb_baseline(config, page)
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
            save_snapshot(
                config.fingerprints.snapshot_dir,
                fingerprint,
                generated_at_commit=head_commit,
                kb_path=page.path.as_posix(),
                kb_last_verified_commit=page.last_verified_commit,
                source_changed_since_kb_last_verified=source_path in changed_since_baseline,
            )
            seen.add(key)
            updated += 1

    return FingerprintUpdateResult(updated=updated, skipped=skipped, accepted=accepted)


def _selected_kb_paths(config: DriftKBConfig, *, kb_file: Path | None, all_kb: bool) -> tuple[Path, ...]:
    if kb_file is not None:
        path = kb_file if kb_file.is_absolute() else config.repo_root / kb_file
        return (path.resolve(),)
    if all_kb:
        return scan_curated_kb_files(config.kb.curated_dir)
    return ()


def _changed_since_kb_baseline(config: DriftKBConfig, page) -> set[str]:
    baseline = page.last_verified_commit
    if baseline is None or not is_fixed_commit_ref(baseline) or not commit_exists(config.repo_root, baseline):
        return set(all_source_files(config))
    try:
        return set(
            repo_paths_relative_to_source_root(
                get_changed_files(config.repo_root, baseline, include_worktree=True),
                config.repo_root,
                config.sources.root,
                include=config.sources.include,
                exclude=config.sources.exclude,
            )
        )
    except GitError:
        return set(all_source_files(config))


def _ensure_covered_sources_clean_at_head(config: DriftKBConfig, kb_path: Path, head_commit: str) -> None:
    page = load_kb_file(kb_path, config)
    try:
        changed = repo_paths_relative_to_source_root(
            get_changed_files(config.repo_root, head_commit, include_worktree=True),
            config.repo_root,
            config.sources.root,
            include=config.sources.include,
            exclude=config.sources.exclude,
        )
    except GitError as exc:
        raise ValueError(str(exc)) from exc
    matched = tuple(path for path in changed if path_matches_any(path, page.source_globs))
    if matched:
        display = ", ".join(matched[:5])
        suffix = "" if len(matched) <= 5 else f", and {len(matched) - 5} more"
        raise ValueError(
            "covered source files have uncommitted changes; commit or discard them "
            f"before using --accept-current: {display}{suffix}"
        )


def _write_last_verified_commit(path: Path, commit: str) -> None:
    frontmatter, body = parse_markdown_frontmatter(path)
    frontmatter = dict(frontmatter)
    frontmatter["last_verified_commit"] = commit
    normalized_body = body if body.endswith("\n") else f"{body}\n"
    path.write_text(f"---\n{dump_simple_yaml(frontmatter)}---\n{normalized_body}", encoding="utf-8")
