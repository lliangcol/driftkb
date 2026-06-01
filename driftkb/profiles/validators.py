from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from driftkb.core.models import KBFile, ValidationIssue, ValidationStatus
from driftkb.core.paths import to_posix_relative

ENTERPRISE_HISTORICAL_DISCLAIMER = "仅作历史参考，不作为当前事实依据"
ENTERPRISE_LEGACY_CONTENT_EXCLUDES = ("legacy/content/**", "legacy/content/**/*")


def validate_profile_rules(config: Any, kb_files: list[KBFile]) -> tuple[ValidationIssue, ...]:
    if config.profile.name != "enterprise-java":
        return ()
    return _validate_enterprise_retrieval_policy(config, kb_files)


def _validate_enterprise_retrieval_policy(config: Any, kb_files: list[KBFile]) -> tuple[ValidationIssue, ...]:
    policy_path = config.retrieval_policy.path
    should_validate = config.retrieval_policy.enabled or policy_path.exists()
    if not should_validate:
        return ()
    if not policy_path.exists():
        return (
            _repo_issue(
                "retrieval_policy_missing",
                "RETRIEVAL_POLICY.json is required when retrieval_policy.enabled is true.",
                config.repo_root,
                policy_path,
            ),
        )

    issues: list[ValidationIssue] = []
    try:
        raw_policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return (
            _repo_issue(
                "retrieval_policy_invalid",
                f"RETRIEVAL_POLICY.json could not be read as JSON: {exc}",
                config.repo_root,
                policy_path,
            ),
        )

    if not isinstance(raw_policy, dict):
        issues.append(
            _repo_issue(
                "retrieval_policy_invalid",
                "RETRIEVAL_POLICY.json must contain a JSON object.",
                config.repo_root,
                policy_path,
            )
        )
        return tuple(issues)

    default_include = raw_policy.get("default_include")
    default_exclude = raw_policy.get("default_exclude")
    if not _string_list(default_include):
        issues.append(
            _repo_issue(
                "retrieval_policy_default_include_invalid",
                "RETRIEVAL_POLICY.json default_include must be a non-empty string array.",
                config.repo_root,
                policy_path,
            )
        )
    if not _string_list(default_exclude):
        issues.append(
            _repo_issue(
                "retrieval_policy_default_exclude_invalid",
                "RETRIEVAL_POLICY.json default_exclude must be a non-empty string array.",
                config.repo_root,
                policy_path,
            )
        )
    elif not any(_excludes_legacy_content(pattern) for pattern in default_exclude):
        issues.append(
            _repo_issue(
                "retrieval_policy_legacy_content_not_excluded",
                "RETRIEVAL_POLICY.json default_exclude must exclude legacy/content historical content.",
                config.repo_root,
                policy_path,
            )
        )

    issues.extend(_validate_historical_disclaimers(config, kb_files))
    return tuple(issues)


def _validate_historical_disclaimers(config: Any, kb_files: list[KBFile]) -> tuple[ValidationIssue, ...]:
    issues: list[ValidationIssue] = []
    for kb_file in kb_files:
        path = kb_file.path.as_posix()
        if not path.startswith("legacy/content/") and "/legacy/content/" not in path:
            continue
        if ENTERPRISE_HISTORICAL_DISCLAIMER in kb_file.body:
            continue
        issues.append(
            ValidationIssue(
                code="historical_content_disclaimer_missing",
                message="legacy/content KB files must include the Chinese historical-only disclaimer.",
                path=kb_file.path,
                severity=ValidationStatus.FAIL,
                metadata={"required_text": ENTERPRISE_HISTORICAL_DISCLAIMER},
            )
        )
    return tuple(issues)


def _repo_issue(code: str, message: str, repo_root: Path, path: Path) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        message=message,
        path=Path(to_posix_relative(path, repo_root)),
        severity=ValidationStatus.FAIL,
    )


def _string_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) for item in value)


def _excludes_legacy_content(pattern: str) -> bool:
    normalized = pattern.strip().replace("\\", "/")
    return any(
        normalized == expected or normalized.endswith(f"/{expected}") for expected in ENTERPRISE_LEGACY_CONTENT_EXCLUDES
    )
