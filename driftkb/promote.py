from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from driftkb.adapters.registry import build_adapters
from driftkb.core.config import DriftKBConfig, dump_simple_yaml
from driftkb.core.frontmatter import normalize_frontmatter_aliases, parse_markdown_frontmatter
from driftkb.core.git import GitError, get_changed_files, get_head_commit, has_staged_changes
from driftkb.core.paths import path_matches_any, repo_paths_relative_to_source_root
from driftkb.fingerprints.update import FingerprintUpdateResult, update_fingerprints

REVIEWED_PROMOTE_STATUS = "human_reviewed"
ALLOWED_PROMOTE_STALE_POLICIES = {"warn", "fail"}


class PromoteError(ValueError):
    """Raised when a generated KB stub cannot be promoted safely."""


@dataclass(frozen=True)
class PromoteResult:
    source_path: Path
    target_path: Path
    head_commit: str
    dry_run: bool
    stale_policy: str
    updated_frontmatter: dict[str, Any]
    fingerprint_update: FingerprintUpdateResult | None = None


def promote_generated_stub(
    config: DriftKBConfig,
    path: Path,
    *,
    stale_policy: str = "fail",
    update_fingerprints_after: bool = False,
    dry_run: bool = False,
) -> PromoteResult:
    stale_policy = stale_policy.lower()
    if stale_policy not in ALLOWED_PROMOTE_STALE_POLICIES:
        raise PromoteError("stale_policy must be one of fail, warn.")

    source_path = _resolve_path(config.repo_root, path)
    generated_relative = _relative_to_generated_dir(source_path, config)
    target_path = (config.kb.curated_dir / generated_relative).resolve()

    if source_path.name.lower() == "readme.md":
        raise PromoteError("generated README files cannot be promoted.")
    if not source_path.is_file():
        raise PromoteError(f"generated KB file does not exist: {_display_path(source_path, config.repo_root)}")
    if target_path.exists():
        raise PromoteError(f"target curated KB already exists: {_display_path(target_path, config.repo_root)}")

    frontmatter, body = parse_markdown_frontmatter(source_path)
    frontmatter = normalize_frontmatter_aliases(frontmatter, config.profile)
    _validate_generated_frontmatter(frontmatter, config)

    try:
        if has_staged_changes(config.repo_root):
            raise PromoteError("git working tree has staged changes; commit or unstage them before promote.")
        head_commit = get_head_commit(config.repo_root)
    except GitError as exc:
        raise PromoteError(str(exc)) from exc

    updated = _promoted_frontmatter(frontmatter, head_commit=head_commit, stale_policy=stale_policy)
    fingerprint_update: FingerprintUpdateResult | None = None
    _ensure_adapters_known(config, updated)
    if update_fingerprints_after:
        _ensure_fingerprint_sources_clean(config, updated, head_commit)

    if not dry_run:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(_render_markdown(updated, body), encoding="utf-8")
        source_path.unlink()
        if update_fingerprints_after:
            fingerprint_update = update_fingerprints(config, kb_file=target_path, all_kb=False)

    return PromoteResult(
        source_path=source_path,
        target_path=target_path,
        head_commit=head_commit,
        dry_run=dry_run,
        stale_policy=stale_policy,
        updated_frontmatter=updated,
        fingerprint_update=fingerprint_update,
    )


def _validate_generated_frontmatter(frontmatter: dict[str, Any], config: DriftKBConfig) -> None:
    if frontmatter.get("kind") != "generated":
        raise PromoteError("only KB files with kind: generated can be promoted.")
    review_status = _review_status(frontmatter, config)
    if review_status not in config.profile.promote_review_statuses:
        expected = ", ".join(config.profile.promote_review_statuses)
        raise PromoteError(f"{config.profile.generated_review_status_field} must be {expected} after human review.")
    reviewed_by = _reviewer(frontmatter, config)
    if not isinstance(reviewed_by, str) or not reviewed_by.strip():
        expected = ", ".join(config.profile.promote_reviewer_fields)
        raise PromoteError(f"{expected} must identify the human reviewer before promotion.")


def _review_status(frontmatter: dict[str, Any], config: DriftKBConfig) -> Any:
    field = config.profile.generated_review_status_field
    if field in frontmatter:
        return frontmatter.get(field)
    return frontmatter.get("validation_status")


def _reviewer(frontmatter: dict[str, Any], config: DriftKBConfig) -> Any:
    for field in config.profile.promote_reviewer_fields:
        if field in frontmatter:
            return frontmatter.get(field)
    return None


def _ensure_fingerprint_sources_clean(
    config: DriftKBConfig,
    frontmatter: dict[str, Any],
    head_commit: str,
) -> None:
    source_globs = _source_globs(frontmatter)
    if not source_globs:
        return

    try:
        changed_paths = repo_paths_relative_to_source_root(
            get_changed_files(config.repo_root, head_commit, include_worktree=True),
            config.repo_root,
            config.sources.root,
        )
    except GitError as exc:
        raise PromoteError(str(exc)) from exc

    matched = tuple(path for path in changed_paths if path_matches_any(path, source_globs))
    if matched:
        display = ", ".join(matched[:5])
        suffix = "" if len(matched) <= 5 else f", and {len(matched) - 5} more"
        raise PromoteError(
            "covered source files have uncommitted changes; commit or discard them "
            f"before using --update-fingerprints: {display}{suffix}"
        )


def _source_globs(frontmatter: dict[str, Any]) -> tuple[str, ...]:
    value = frontmatter.get("source_globs", [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise PromoteError("source_globs must be a list of strings.")
    return tuple(value)


def _ensure_adapters_known(config: DriftKBConfig, frontmatter: dict[str, Any]) -> None:
    adapter_names = _adapter_names(frontmatter) or config.adapters.enabled
    try:
        build_adapters(adapter_names)
    except ValueError as exc:
        raise PromoteError(str(exc)) from exc


def _adapter_names(frontmatter: dict[str, Any]) -> tuple[str, ...]:
    value = frontmatter.get("adapters", [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise PromoteError("adapters must be a list of strings.")
    return tuple(value)


def _promoted_frontmatter(frontmatter: dict[str, Any], *, head_commit: str, stale_policy: str) -> dict[str, Any]:
    promoted = dict(frontmatter)
    promoted["kind"] = "curated"
    promoted["last_verified_commit"] = head_commit
    promoted["stale_policy"] = stale_policy
    for key in (
        "generated_from_commit",
        "generator",
        "validation_status",
        "review_status",
        "reviewed_by",
        "reviewer",
        "reviewed_at",
        "anchor_classes",
    ):
        promoted.pop(key, None)
    return promoted


def _render_markdown(frontmatter: dict[str, Any], body: str) -> str:
    normalized_body = body if body.endswith("\n") else f"{body}\n"
    return f"---\n{dump_simple_yaml(frontmatter)}---\n{normalized_body}"


def _relative_to_generated_dir(path: Path, config: DriftKBConfig) -> Path:
    try:
        return path.relative_to(config.kb.generated_dir)
    except ValueError as exc:
        raise PromoteError(
            f"promote only accepts files under {_display_path(config.kb.generated_dir, config.repo_root)}."
        ) from exc


def _resolve_path(repo_root: Path, path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (repo_root / path).resolve()


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()
