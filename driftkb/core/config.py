from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from driftkb.core.models import ProfileConfig
from driftkb.profiles import DEFAULT_PROFILE, get_profile, get_profile_defaults

DEFAULT_CONFIG_DIR = ".driftkb"
DEFAULT_CONFIG_PATH = Path(DEFAULT_CONFIG_DIR) / "config.yml"
DEFAULT_CURATED_KB_DIR = "docs/kb/curated"
DEFAULT_GENERATED_KB_DIR = "docs/kb/generated"
DEFAULT_VALIDATION_DIR = ".driftkb/validation"

DEFAULT_CONFIG_DATA: dict[str, Any] = {
    "version": 1,
    "kb": {
        "curated_dir": DEFAULT_CURATED_KB_DIR,
        "generated_dir": DEFAULT_GENERATED_KB_DIR,
        "validation_dir": DEFAULT_VALIDATION_DIR,
    },
    "sources": {
        "root": ".",
        "include": ["src/**/*"],
        "exclude": ["**/.git/**"],
    },
    "validation": {
        "default_stale_policy": "warn",
        "report_path": ".driftkb/validation/last-run.json",
    },
    "retrieval_policy": {
        "enabled": False,
        "path": "RETRIEVAL_POLICY.json",
    },
    "verify": {
        "enabled": True,
        "allow_shell": False,
        "timeout_seconds": 10,
    },
    "graph": {
        "cache_path": ".driftkb/call_graph_cache.json",
    },
    "fingerprints": {
        "enabled": True,
        "snapshot_dir": ".driftkb/validation/fingerprints",
    },
    "adapters": {
        "enabled": ["generic"],
    },
    "gaps": {
        "enabled": True,
        "whitelist_path": ".driftkb/gap_whitelist.txt",
        "risk_patterns": [],
    },
}


class ConfigError(ValueError):
    """Raised when `.driftkb/config.yml` cannot be read or parsed."""


@dataclass(frozen=True)
class KBConfig:
    curated_dir: Path
    generated_dir: Path
    validation_dir: Path


@dataclass(frozen=True)
class SourcesConfig:
    root: Path
    include: tuple[str, ...] = ("src/**/*",)
    exclude: tuple[str, ...] = ("**/.git/**",)


@dataclass(frozen=True)
class ValidationConfig:
    default_stale_policy: str = "warn"
    report_path: Path = Path(".driftkb/validation/last-run.json")


@dataclass(frozen=True)
class RetrievalPolicyConfig:
    enabled: bool = False
    path: Path = Path("RETRIEVAL_POLICY.json")


@dataclass(frozen=True)
class VerifyConfig:
    enabled: bool = True
    allow_shell: bool = False
    timeout_seconds: float = 10


@dataclass(frozen=True)
class GraphConfig:
    cache_path: Path = Path(".driftkb/call_graph_cache.json")
    kb_section_map_path: Path | None = None


@dataclass(frozen=True)
class FingerprintsConfig:
    enabled: bool = True
    snapshot_dir: Path = Path(".driftkb/validation/fingerprints")


@dataclass(frozen=True)
class AdaptersConfig:
    enabled: tuple[str, ...] = ("generic",)


@dataclass(frozen=True)
class GapsConfig:
    enabled: bool = True
    whitelist_path: Path = Path(".driftkb/gap_whitelist.txt")
    risk_patterns: tuple[str, ...] = ()


@dataclass(frozen=True)
class DriftKBConfig:
    repo_root: Path
    path: Path
    version: int
    profile: ProfileConfig
    kb: KBConfig
    sources: SourcesConfig
    validation: ValidationConfig
    retrieval_policy: RetrievalPolicyConfig
    verify: VerifyConfig
    graph: GraphConfig
    fingerprints: FingerprintsConfig
    adapters: AdaptersConfig
    gaps: GapsConfig
    extra: dict[str, Any] = field(default_factory=dict)


def create_default_config(repo_root: Path, profile: str | None = None) -> Path:
    repo_root = repo_root.resolve()
    config_path = repo_root / DEFAULT_CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        profile_config = get_profile(profile)
        profile_defaults = get_profile_defaults(profile_config.name)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc

    data = _deep_merge(DEFAULT_CONFIG_DATA, profile_defaults)
    if profile_config.name != DEFAULT_PROFILE:
        data = {"profile": profile_config.name, **data}

    kb_defaults = data["kb"]
    validation_defaults = data["validation"]
    fingerprints_defaults = data["fingerprints"]
    for directory in (
        repo_root / _string(kb_defaults, "curated_dir"),
        repo_root / _string(kb_defaults, "generated_dir"),
        repo_root / _string(kb_defaults, "validation_dir"),
        repo_root / Path(_string(validation_defaults, "report_path")).parent,
        repo_root / _string(fingerprints_defaults, "snapshot_dir"),
    ):
        directory.mkdir(parents=True, exist_ok=True)

    if not config_path.exists():
        config_path.write_text(dump_simple_yaml(data), encoding="utf-8")

    return config_path


def load_config(repo_root: Path, config_path: Path | None = None, profile: str | None = None) -> DriftKBConfig:
    repo_root = repo_root.resolve()
    config_path = _resolve_repo_path(repo_root, str(config_path), "config") if config_path else repo_root / DEFAULT_CONFIG_PATH

    if config_path.exists():
        raw = parse_simple_yaml(config_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ConfigError(f"{config_path} must contain a YAML mapping.")
    else:
        raw = {}

    configured_profile = _profile_name(raw, explicit_profile=profile)
    try:
        profile_config = get_profile(configured_profile)
        profile_defaults = get_profile_defaults(configured_profile)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc

    data = _deep_merge(_deep_merge(DEFAULT_CONFIG_DATA, profile_defaults), raw)
    data["profile"] = profile_config.name
    known_keys = {*DEFAULT_CONFIG_DATA, "profile"}
    extra = {key: value for key, value in data.items() if key not in known_keys}

    kb = _mapping(data, "kb")
    sources = _mapping(data, "sources")
    validation = _mapping(data, "validation")
    retrieval_policy = _mapping(data, "retrieval_policy")
    verify = _mapping(data, "verify")
    graph = _mapping(data, "graph")
    fingerprints = _mapping(data, "fingerprints")
    adapters = _mapping(data, "adapters")
    gaps = _mapping(data, "gaps")

    return DriftKBConfig(
        repo_root=repo_root,
        path=config_path,
        version=_int(data, "version"),
        profile=profile_config,
        kb=KBConfig(
            curated_dir=_resolve_repo_path(repo_root, _string(kb, "curated_dir"), "kb.curated_dir"),
            generated_dir=_resolve_repo_path(repo_root, _string(kb, "generated_dir"), "kb.generated_dir"),
            validation_dir=_resolve_repo_path(repo_root, _string(kb, "validation_dir"), "kb.validation_dir"),
        ),
        sources=SourcesConfig(
            root=_resolve_repo_path(repo_root, _string(sources, "root"), "sources.root"),
            include=tuple(_string_list(sources, "include")),
            exclude=tuple(_string_list(sources, "exclude")),
        ),
        validation=ValidationConfig(
            default_stale_policy=_normalize_stale_policy(
                _string(validation, "default_stale_policy"),
                profile_config,
                "validation.default_stale_policy",
            ),
            report_path=_resolve_repo_path(repo_root, _string(validation, "report_path"), "validation.report_path"),
        ),
        retrieval_policy=RetrievalPolicyConfig(
            enabled=_bool(retrieval_policy, "enabled"),
            path=_resolve_repo_path(repo_root, _string(retrieval_policy, "path"), "retrieval_policy.path"),
        ),
        verify=VerifyConfig(
            enabled=_bool(verify, "enabled"),
            allow_shell=_bool(verify, "allow_shell"),
            timeout_seconds=_positive_float(verify, "timeout_seconds"),
        ),
        graph=GraphConfig(
            cache_path=_resolve_repo_path(repo_root, _string(graph, "cache_path"), "graph.cache_path"),
            kb_section_map_path=_optional_repo_path(
                repo_root,
                graph.get("kb_section_map_path"),
                "graph.kb_section_map_path",
            ),
        ),
        fingerprints=FingerprintsConfig(
            enabled=_bool(fingerprints, "enabled"),
            snapshot_dir=_resolve_repo_path(repo_root, _string(fingerprints, "snapshot_dir"), "fingerprints.snapshot_dir"),
        ),
        adapters=AdaptersConfig(enabled=tuple(_string_list(adapters, "enabled"))),
        gaps=GapsConfig(
            enabled=_bool(gaps, "enabled"),
            whitelist_path=_resolve_repo_path(repo_root, _string(gaps, "whitelist_path"), "gaps.whitelist_path"),
            risk_patterns=tuple(_string_list(gaps, "risk_patterns")),
        ),
        extra=extra,
    )


def _profile_name(raw: dict[str, Any], *, explicit_profile: str | None) -> str:
    if explicit_profile is not None:
        return explicit_profile
    value = raw.get("profile", DEFAULT_PROFILE)
    if not isinstance(value, str):
        raise ConfigError("Configuration key `profile` must be a string.")
    return value


def _normalize_stale_policy(value: str, profile: ProfileConfig, field: str) -> str:
    normalized = profile.stale_policy_aliases.get(value, value)
    if normalized not in {"warn", "fail", "skip"}:
        raise ConfigError(f"Configuration key `{field}` must be one of: fail, skip, warn.")
    return normalized


def parse_simple_yaml(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]

    for line_number, raw_line in enumerate(lines, start=1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        if indent % 2 != 0:
            raise ConfigError(f"YAML indentation must use multiples of 2 spaces at line {line_number}.")
        line = raw_line.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]

        if line.startswith("- "):
            if not isinstance(parent, list):
                raise ConfigError(f"Unexpected list item at line {line_number}.")
            parent.append(_parse_scalar(line[2:].strip()))
            continue

        key, separator, value = line.partition(":")
        if not separator:
            raise ConfigError(f"Expected key/value mapping at line {line_number}.")
        key = key.strip()
        value = value.strip()

        if not isinstance(parent, dict):
            raise ConfigError(f"Cannot add mapping under a list at line {line_number}.")

        if value:
            parent[key] = _parse_scalar(value)
            continue

        next_container: Any = _container_for_next_line(lines, line_number - 1, indent)
        parent[key] = next_container
        stack.append((indent, next_container))

    return root


def dump_simple_yaml(data: dict[str, Any], indent: int = 0) -> str:
    lines: list[str] = []
    prefix = " " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(dump_simple_yaml(value, indent + 2).rstrip("\n"))
        elif isinstance(value, list):
            if value:
                lines.append(f"{prefix}{key}:")
                for item in value:
                    lines.append(f"{prefix}  - {_format_scalar(item)}")
            else:
                lines.append(f"{prefix}{key}: []")
        else:
            lines.append(f"{prefix}{key}: {_format_scalar(value)}")
    return "\n".join(lines) + "\n"


def _container_for_next_line(lines: list[str], current_index: int, current_indent: int) -> Any:
    for raw_line in lines[current_index + 1 :]:
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        next_indent = len(raw_line) - len(raw_line.lstrip(" "))
        if next_indent <= current_indent:
            return {}
        return [] if raw_line.strip().startswith("- ") else {}
    return {}


def _parse_scalar(value: str) -> Any:
    if value == "[]":
        return []
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def _format_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    text = str(value)
    if any(char in text for char in (":", "#", "*")) or text.startswith((" ", "{", "[", "@", "`")):
        return f'"{text}"'
    return text


def _deep_merge(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(defaults)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ConfigError(f"Configuration key `{key}` must be a mapping.")
    return value


def _string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise ConfigError(f"Configuration key `{key}` must be a string.")
    return value


def _string_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"Configuration key `{key}` must be a list of strings.")
    return value


def _bool(data: dict[str, Any], key: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise ConfigError(f"Configuration key `{key}` must be a boolean.")
    return value


def _int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigError(f"Configuration key `{key}` must be an integer.")
    return value


def _positive_float(data: dict[str, Any], key: str) -> float:
    value = data.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ConfigError(f"Configuration key `{key}` must be a number.")
    result = float(value)
    if result <= 0:
        raise ConfigError(f"Configuration key `{key}` must be greater than 0.")
    return result


def _resolve_repo_path(repo_root: Path, value: str, field: str) -> Path:
    path = Path(value)
    resolved = path.resolve() if path.is_absolute() else (repo_root / path).resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ConfigError(f"Configuration key `{field}` must stay inside the repository root.") from exc
    return resolved


def _optional_repo_path(repo_root: Path, value: Any, field: str) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"Configuration key `{field}` must be a string.")
    return _resolve_repo_path(repo_root, value, field)
