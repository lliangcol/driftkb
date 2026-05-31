from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from driftkb.adapters.registry import build_adapters
from driftkb.core.config import ConfigError, DriftKBConfig
from driftkb.core.frontmatter import FrontmatterError, normalize_frontmatter_aliases, parse_markdown_frontmatter
from driftkb.core.git import GitError, commit_exists, get_changed_files, get_head_commit
from driftkb.core.models import KBFile, ValidationIssue, ValidationResult, ValidationStatus
from driftkb.core.paths import (
    path_matches_any,
    repo_paths_relative_to_source_root,
    to_posix_relative,
)
from driftkb.fingerprints.snapshots import compare_fingerprint, load_snapshot
from driftkb.graph.cache import CallGraphCache, load_graph_cache
from driftkb.profiles.validators import validate_profile_rules
from driftkb.verify.blocks import extract_verify_blocks, run_verify_block

ALLOWED_STALE_POLICIES = {"warn", "fail", "skip"}
REVIEWED_CHANGE_SCOPE_MATCHED_DIRTY_PATHS = "matched_dirty_paths"
ALLOWED_REVIEWED_CHANGE_SCOPES = {REVIEWED_CHANGE_SCOPE_MATCHED_DIRTY_PATHS}


def apply_validate_overrides(
    config: DriftKBConfig,
    *,
    kb_dir: Path | None = None,
    source_root: Path | None = None,
    report_path: Path | None = None,
    verify_enabled: bool | None = None,
    allow_shell_verify: bool | None = None,
    verify_timeout_seconds: float | None = None,
) -> DriftKBConfig:
    repo_root = config.repo_root
    if kb_dir is not None:
        config = replace(config, kb=replace(config.kb, curated_dir=_resolve_cli_path(repo_root, kb_dir)))
    if source_root is not None:
        config = replace(config, sources=replace(config.sources, root=_resolve_cli_path(repo_root, source_root)))
    if report_path is not None:
        config = replace(
            config,
            validation=replace(config.validation, report_path=_resolve_cli_path(repo_root, report_path)),
        )
    if verify_enabled is not None:
        config = replace(config, verify=replace(config.verify, enabled=verify_enabled))
    if allow_shell_verify is not None:
        config = replace(config, verify=replace(config.verify, allow_shell=allow_shell_verify))
    if verify_timeout_seconds is not None:
        config = replace(config, verify=replace(config.verify, timeout_seconds=verify_timeout_seconds))
    return config


def validate_kb(config: DriftKBConfig) -> ValidationResult:
    warnings: list[ValidationIssue] = []
    stale: list[ValidationIssue] = []
    verify: list[ValidationIssue] = []
    kb_files: list[KBFile] = []
    direct_hit_kbs: list[KBFile] = []

    try:
        checked_at_commit = get_head_commit(config.repo_root)
    except GitError as exc:
        return ValidationResult(
            result=ValidationStatus.WARN,
            checked_at_commit=None,
            warnings=(
                ValidationIssue(
                    code="git_head_unavailable",
                    message=str(exc),
                    severity=ValidationStatus.WARN,
                ),
            ),
        )

    graph_cache = load_graph_cache(config.graph.cache_path)

    for kb_path in scan_curated_kb_files(config.kb.curated_dir):
        try:
            kb_files.append(load_kb_file(kb_path, config))
        except FrontmatterError as exc:
            warnings.append(
                ValidationIssue(
                    code="frontmatter_invalid",
                    message=str(exc),
                    path=_relative_report_path(kb_path, config.repo_root),
                    severity=ValidationStatus.FAIL,
                )
            )
            continue

    _validate_adapter_names(config, kb_files)
    warnings.extend(validate_profile_rules(config, kb_files))

    for kb_file in kb_files:
        if config.verify.enabled:
            verify.extend(_run_verify_blocks(kb_file, config))

        if kb_file.stale_policy == "skip":
            continue

        if not kb_file.last_verified_commit:
            warnings.append(
                _issue(
                    "last_verified_commit_missing",
                    "last_verified_commit is missing",
                    kb_file,
                    ValidationStatus.WARN,
                )
            )
            continue

        baseline_exists = commit_exists(config.repo_root, kb_file.last_verified_commit)
        if baseline_exists:
            try:
                changed_files = repo_paths_relative_to_source_root(
                    get_changed_files(config.repo_root, kb_file.last_verified_commit, include_worktree=True),
                    config.repo_root,
                    config.sources.root,
                )
            except GitError as exc:
                warnings.append(
                    _issue(
                        "git_diff_failed",
                        str(exc),
                        kb_file,
                        ValidationStatus.WARN,
                    )
                )
                changed_files = all_source_files(config)
        else:
            warnings.append(
                _issue(
                    "last_verified_commit_missing_in_git",
                    "last_verified_commit does not exist in this repository; using a conservative source scan",
                    kb_file,
                    ValidationStatus.WARN,
                )
            )
            changed_files = all_source_files(config)

        candidate_paths = tuple(
            path for path in changed_files if path_matches_any(path, kb_file.source_globs)
        )
        matched_paths = _paths_without_equal_fingerprint_snapshots(candidate_paths, kb_file, config)
        matched_paths, reviewed_issues = _apply_reviewed_path_exemptions(matched_paths, kb_file)
        warnings.extend(reviewed_issues)
        if not matched_paths:
            continue

        direct_hit_kbs.append(kb_file)
        severity = ValidationStatus.FAIL if kb_file.stale_policy == "fail" else ValidationStatus.WARN
        issue = _issue(
            "source_changed",
            "source changed since last_verified_commit",
            kb_file,
            severity,
            metadata={"matched_paths": matched_paths},
        )
        if severity == ValidationStatus.FAIL:
            stale.append(issue)
        else:
            warnings.append(issue)

    warnings.extend(_graph_propagation_warnings(direct_hit_kbs, kb_files, graph_cache, warnings, stale))

    result = _overall_status(warnings, stale, verify)
    return ValidationResult(
        result=result,
        checked_at_commit=checked_at_commit,
        stale=tuple(stale),
        warnings=tuple(warnings),
        verify=tuple(verify),
        metadata={
            "kb_dir": _safe_relative(config.kb.curated_dir, config.repo_root),
            "source_root": _safe_relative(config.sources.root, config.repo_root),
            "graph_cache": graph_cache.metadata,
        },
    )


def scan_curated_kb_files(kb_dir: Path) -> tuple[Path, ...]:
    if not kb_dir.exists():
        return ()
    return tuple(sorted(path for path in kb_dir.rglob("*.md") if path.is_file()))


def load_kb_file(path: Path, config: DriftKBConfig) -> KBFile:
    frontmatter, body = parse_markdown_frontmatter(path)
    frontmatter = normalize_frontmatter_aliases(frontmatter, config.profile)
    stale_policy = _frontmatter_string(
        frontmatter,
        "stale_policy",
        config.validation.default_stale_policy,
    ).lower()
    stale_policy = config.profile.stale_policy_aliases.get(stale_policy, stale_policy)
    if stale_policy not in ALLOWED_STALE_POLICIES:
        raise FrontmatterError(
            f"stale_policy must be one of {', '.join(sorted(ALLOWED_STALE_POLICIES))}."
        )
    return KBFile(
        path=_relative_report_path(path, config.repo_root),
        frontmatter=frontmatter,
        body=body,
        last_verified_commit=_optional_string(frontmatter, "last_verified_commit"),
        source_globs=tuple(_string_list(frontmatter, "source_globs")),
        stale_policy=stale_policy,
        anchor_symbols=tuple(_string_list(frontmatter, "anchor_symbols")),
        propagate_callers=_propagate_bool(frontmatter, "callers"),
        propagate_callees=_propagate_bool(frontmatter, "callees"),
        adapters=tuple(_string_list(frontmatter, "adapters")),
        owner=_optional_string(frontmatter, "owner"),
        tags=tuple(_string_list(frontmatter, "tags")),
        reviewed_change_scope=_optional_string(frontmatter, "reviewed_change_scope"),
        reviewed_at=_optional_string(frontmatter, "reviewed_at"),
        reviewed_paths=tuple(_string_list(frontmatter, "reviewed_paths")),
    )


def all_source_files(config: DriftKBConfig) -> tuple[str, ...]:
    if not config.sources.root.exists():
        return ()
    files: list[str] = []
    for path in config.sources.root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(config.sources.root).as_posix()
        if path_matches_any(relative, config.sources.exclude):
            continue
        if config.sources.include and not path_matches_any(relative, config.sources.include):
            continue
        files.append(relative)
    return tuple(sorted(files))


def _paths_without_equal_fingerprint_snapshots(
    paths: tuple[str, ...],
    kb_file: KBFile,
    config: DriftKBConfig,
) -> tuple[str, ...]:
    if not config.fingerprints.enabled or not paths:
        return paths

    stale_paths: list[str] = []
    adapter_names = kb_file.adapters or config.adapters.enabled
    adapters = build_adapters(adapter_names)
    for source_path in paths:
        absolute = config.sources.root / source_path
        adapter = next((item for item in adapters if item.supports(absolute)), None)
        if adapter is None:
            stale_paths.append(source_path)
            continue
        try:
            current = adapter.extract(absolute, config.sources.root)
            snapshot = load_snapshot(config.fingerprints.snapshot_dir, current.file, current.adapter)
        except (OSError, UnicodeError, ValueError):
            stale_paths.append(source_path)
            continue
        if not compare_fingerprint(current, snapshot):
            stale_paths.append(source_path)
    return tuple(stale_paths)


def _apply_reviewed_path_exemptions(
    matched_paths: tuple[str, ...],
    kb_file: KBFile,
) -> tuple[tuple[str, ...], list[ValidationIssue]]:
    if not kb_file.reviewed_paths and kb_file.reviewed_change_scope is None and kb_file.reviewed_at is None:
        return matched_paths, []

    issues: list[ValidationIssue] = []
    if kb_file.reviewed_change_scope not in ALLOWED_REVIEWED_CHANGE_SCOPES:
        expected = ", ".join(sorted(ALLOWED_REVIEWED_CHANGE_SCOPES))
        issues.append(
            _issue(
                "reviewed_change_scope_invalid",
                f"reviewed_change_scope must be one of: {expected}",
                kb_file,
                ValidationStatus.FAIL,
            )
        )

    if not kb_file.reviewed_at:
        issues.append(
            _issue(
                "reviewed_at_missing",
                "reviewed_at is required when using reviewed_paths",
                kb_file,
                ValidationStatus.FAIL,
            )
        )

    reviewed_paths = kb_file.reviewed_paths
    outside_source_globs = tuple(
        path for path in reviewed_paths if not path_matches_any(path, kb_file.source_globs)
    )
    if outside_source_globs:
        issues.append(
            _issue(
                "reviewed_paths_outside_source_globs",
                "reviewed_paths must be inside source_globs",
                kb_file,
                ValidationStatus.FAIL,
                metadata={"reviewed_paths": outside_source_globs},
            )
        )

    matched_path_set = set(matched_paths)
    non_current_paths = tuple(path for path in reviewed_paths if path not in matched_path_set)
    if non_current_paths:
        issues.append(
            _issue(
                "reviewed_paths_not_current_dirty",
                "reviewed_paths can only cover current matched dirty paths",
                kb_file,
                ValidationStatus.FAIL,
                metadata={"reviewed_paths": non_current_paths, "matched_paths": matched_paths},
            )
        )

    if issues:
        return matched_paths, issues

    reviewed_path_set = set(reviewed_paths)
    return tuple(path for path in matched_paths if path not in reviewed_path_set), []


def _validate_adapter_names(config: DriftKBConfig, kb_files: list[KBFile]) -> None:
    build_adapters(config.adapters.enabled)
    for kb_file in kb_files:
        if kb_file.adapters:
            build_adapters(kb_file.adapters)


def _overall_status(
    warnings: list[ValidationIssue],
    stale: list[ValidationIssue],
    verify: list[ValidationIssue],
) -> ValidationStatus:
    if any(issue.severity == ValidationStatus.FAIL for issue in (*warnings, *stale, *verify)):
        return ValidationStatus.FAIL
    if warnings or any(issue.severity == ValidationStatus.WARN for issue in verify):
        return ValidationStatus.WARN
    return ValidationStatus.PASS


def _run_verify_blocks(kb_file: KBFile, config: DriftKBConfig) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for block in extract_verify_blocks(kb_file.body):
        result = run_verify_block(
            block,
            config.sources.root,
            allow_shell=config.verify.allow_shell,
            timeout_seconds=config.verify.timeout_seconds,
        )
        issues.append(
            ValidationIssue(
                code=_verify_code(result.result),
                message=result.message,
                path=kb_file.path,
                severity=result.result,
                metadata={
                    "kb_file": kb_file.path.as_posix(),
                    "block_index": result.block_index,
                    "command": result.command,
                    "expected": result.expected,
                    "actual_match_count": result.actual_match_count,
                    "result": result.result.value,
                    "stdout_sample": result.stdout_sample,
                    "stderr_sample": result.stderr_sample,
                },
            )
        )
    return issues


def _graph_propagation_warnings(
    direct_hit_kbs: list[KBFile],
    kb_files: list[KBFile],
    graph_cache: CallGraphCache,
    existing_warnings: list[ValidationIssue],
    stale: list[ValidationIssue],
) -> list[ValidationIssue]:
    if not direct_hit_kbs or not graph_cache.nodes:
        return []

    by_anchor: dict[str, list[KBFile]] = {}
    for kb_file in kb_files:
        for symbol in kb_file.anchor_symbols:
            by_anchor.setdefault(symbol, []).append(kb_file)

    existing_paths = {
        issue.path.as_posix()
        for issue in (*existing_warnings, *stale)
        if issue.path is not None and issue.code in {"source_changed", "graph_propagated"}
    }
    emitted_paths: set[str] = set()
    propagated: list[ValidationIssue] = []

    for source_kb in direct_hit_kbs:
        related_symbols: set[str] = set()
        for anchor_symbol in source_kb.anchor_symbols:
            if source_kb.propagate_callers:
                related_symbols.update(graph_cache.get_callers(anchor_symbol))
            if source_kb.propagate_callees:
                related_symbols.update(graph_cache.get_callees(anchor_symbol))

        for related_symbol in sorted(related_symbols):
            for target_kb in by_anchor.get(related_symbol, []):
                target_path = target_kb.path.as_posix()
                if target_path == source_kb.path.as_posix():
                    continue
                if target_path in existing_paths or target_path in emitted_paths:
                    continue
                emitted_paths.add(target_path)
                propagated.append(
                    _issue(
                        "graph_propagated",
                        "related anchor symbol may be affected by changed source",
                        target_kb,
                        ValidationStatus.WARN,
                        metadata={
                            "source_kb": source_kb.path.as_posix(),
                            "related_anchor_symbol": related_symbol,
                            "via": "call_graph_cache",
                        },
                    )
                )
    return propagated


def _verify_code(status: ValidationStatus) -> str:
    if status == ValidationStatus.FAIL:
        return "verify_block_failed"
    if status == ValidationStatus.WARN:
        return "verify_block_warn"
    return "verify_block_pass"


def _issue(
    code: str,
    message: str,
    kb_file: KBFile,
    severity: ValidationStatus,
    metadata: dict[str, Any] | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        message=message,
        path=kb_file.path,
        severity=severity,
        metadata=metadata or {},
    )


def _frontmatter_string(frontmatter: dict[str, Any], key: str, default: str) -> str:
    value = frontmatter.get(key, default)
    if not isinstance(value, str):
        raise FrontmatterError(f"{key} must be a string.")
    return value


def _optional_string(frontmatter: dict[str, Any], key: str) -> str | None:
    value = frontmatter.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise FrontmatterError(f"{key} must be a string.")
    return value


def _string_list(frontmatter: dict[str, Any], key: str) -> list[str]:
    value = frontmatter.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise FrontmatterError(f"{key} must be a list of strings.")
    return value


def _propagate_bool(frontmatter: dict[str, Any], key: str) -> bool:
    propagate = frontmatter.get("propagate", {})
    if propagate is None:
        return False
    if not isinstance(propagate, dict):
        raise FrontmatterError("propagate must be a mapping.")
    value = propagate.get(key, False)
    if not isinstance(value, bool):
        raise FrontmatterError(f"propagate.{key} must be a boolean.")
    return value


def _relative_report_path(path: Path, repo_root: Path) -> Path:
    try:
        return Path(to_posix_relative(path, repo_root))
    except ValueError:
        return path


def _safe_relative(path: Path, repo_root: Path) -> str:
    try:
        return to_posix_relative(path, repo_root)
    except ValueError:
        return path.as_posix()


def _resolve_cli_path(repo_root: Path, path: Path) -> Path:
    resolved = path.resolve() if path.is_absolute() else (repo_root / path).resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ConfigError(f"path must stay inside repo root: {path}") from exc
    return resolved
