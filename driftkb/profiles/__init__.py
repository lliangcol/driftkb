from __future__ import annotations

from copy import deepcopy
from typing import Any

from driftkb.core.models import ProfileConfig

DEFAULT_PROFILE = "default"

ENTERPRISE_JAVA_PROFILE_DEFAULTS: dict[str, Any] = {
    "kb": {
        "curated_dir": ".agents/kb/zh/curated",
        "generated_dir": ".agents/kb/zh/generated",
        "validation_dir": ".agents/kb/zh/_validation",
    },
    "validation": {
        "report_path": ".agents/kb/zh/_validation/last-run.json",
    },
    "graph": {
        "cache_path": ".agents/kb/zh/_validation/call_graph_cache.json",
        "kb_section_map_path": ".agents/kb/zh/_validation/kb_section_map.json",
    },
    "fingerprints": {
        "snapshot_dir": ".agents/kb/zh/_validation/fingerprints",
    },
    "adapters": {
        "enabled": ["generic", "enterprise-java"],
    },
    "gaps": {
        "risk_patterns": [
            "@DS",
            "@Transactional",
            "@RocketMQMessageListener",
            "@XxlJob",
        ],
    },
}

ENTERPRISE_JAVA_PROFILE = ProfileConfig(
    name="enterprise-java",
    stale_policy_aliases={
        "fail_on_source_change": "fail",
        "warn_on_source_change": "warn",
    },
    frontmatter_aliases={
        "anchor_classes": "anchor_symbols",
    },
    generated_anchor_field="anchor_classes",
    generated_review_status_field="review_status",
    generated_pending_review_status="pending_review",
    promote_review_statuses=("human_reviewed", "reviewed"),
    promote_reviewer_fields=("reviewed_by", "reviewer"),
)

PROFILE_DEFAULTS: dict[str, dict[str, Any]] = {
    DEFAULT_PROFILE: {},
    ENTERPRISE_JAVA_PROFILE.name: ENTERPRISE_JAVA_PROFILE_DEFAULTS,
}

PROFILES: dict[str, ProfileConfig] = {
    DEFAULT_PROFILE: ProfileConfig(),
    ENTERPRISE_JAVA_PROFILE.name: ENTERPRISE_JAVA_PROFILE,
}


def get_profile(name: str | None) -> ProfileConfig:
    profile_name = name or DEFAULT_PROFILE
    try:
        return PROFILES[profile_name]
    except KeyError as exc:
        choices = ", ".join(sorted(PROFILES))
        raise ValueError(f"unknown profile `{profile_name}`; expected one of: {choices}") from exc


def get_profile_defaults(name: str | None) -> dict[str, Any]:
    profile_name = name or DEFAULT_PROFILE
    if profile_name not in PROFILE_DEFAULTS:
        get_profile(profile_name)
    return deepcopy(PROFILE_DEFAULTS[profile_name])


def available_profiles() -> tuple[str, ...]:
    return tuple(sorted(PROFILES))
