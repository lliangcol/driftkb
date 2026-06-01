from __future__ import annotations

from pathlib import Path

import pytest

from driftkb.core.config import ConfigError, create_default_config, load_config


def test_create_default_config_writes_expected_layout(tmp_path: Path) -> None:
    config_path = create_default_config(tmp_path)

    assert config_path == tmp_path / ".driftkb" / "config.yml"
    assert (tmp_path / "docs" / "kb" / "curated").is_dir()
    assert (tmp_path / "docs" / "kb" / "generated").is_dir()
    assert (tmp_path / ".driftkb" / "validation").is_dir()
    assert (tmp_path / ".driftkb" / "validation" / "fingerprints").is_dir()

    config_text = config_path.read_text(encoding="utf-8")
    assert "version: 1" in config_text
    assert "curated_dir: docs/kb/curated" in config_text
    assert '    - "src/**/*"' in config_text
    assert '    - "**/.git/**"' in config_text
    assert "allow_shell: false" in config_text
    assert "retrieval_policy:" in config_text
    assert "path: RETRIEVAL_POLICY.json" in config_text
    assert "snapshot_dir: .driftkb/validation/fingerprints" in config_text
    assert "whitelist_path: .driftkb/gap_whitelist.txt" in config_text
    assert "risk_patterns: []" in config_text


def test_load_config_merges_defaults_and_normalizes_paths(tmp_path: Path) -> None:
    config_path = tmp_path / ".driftkb" / "config.yml"
    config_path.parent.mkdir()
    config_path.write_text(
        """
version: 1
kb:
  curated_dir: knowledge/curated
sources:
  include:
    - "app/**/*.py"
verify:
  enabled: false
""".lstrip(),
        encoding="utf-8",
    )

    config = load_config(tmp_path)

    assert config.kb.curated_dir == (tmp_path / "knowledge" / "curated").resolve()
    assert config.kb.generated_dir == (tmp_path / "docs" / "kb" / "generated").resolve()
    assert config.sources.include == ("app/**/*.py",)
    assert config.sources.exclude == ("**/.git/**",)
    assert config.verify.enabled is False
    assert config.verify.allow_shell is False
    assert config.fingerprints.enabled is True
    assert config.fingerprints.snapshot_dir == (tmp_path / ".driftkb" / "validation" / "fingerprints").resolve()
    assert config.adapters.enabled == ("generic",)
    assert config.gaps.enabled is True
    assert config.gaps.whitelist_path == (tmp_path / ".driftkb" / "gap_whitelist.txt").resolve()
    assert config.gaps.risk_patterns == ()


def test_load_config_uses_defaults_when_config_is_missing(tmp_path: Path) -> None:
    config = load_config(tmp_path)

    assert config.path == (tmp_path / ".driftkb" / "config.yml").resolve()
    assert config.profile.name == "default"
    assert config.kb.curated_dir == (tmp_path / "docs" / "kb" / "curated").resolve()
    assert config.validation.default_stale_policy == "warn"
    assert config.retrieval_policy.enabled is False
    assert config.retrieval_policy.path == (tmp_path / "RETRIEVAL_POLICY.json").resolve()
    assert config.gaps.risk_patterns == ()


def test_load_config_applies_configured_enterprise_java_profile_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / ".driftkb" / "config.yml"
    config_path.parent.mkdir()
    config_path.write_text(
        """
version: 1
profile: enterprise-java
validation:
  default_stale_policy: fail_on_source_change
""".lstrip(),
        encoding="utf-8",
    )

    config = load_config(tmp_path)

    assert config.profile.name == "enterprise-java"
    assert config.kb.curated_dir == (tmp_path / ".agents" / "kb" / "zh" / "curated").resolve()
    assert config.kb.generated_dir == (tmp_path / ".agents" / "kb" / "zh" / "generated").resolve()
    assert config.kb.validation_dir == (tmp_path / ".agents" / "kb" / "zh" / "_validation").resolve()
    assert config.validation.default_stale_policy == "fail"
    assert (
        config.validation.report_path
        == (tmp_path / ".agents" / "kb" / "zh" / "_validation" / "last-run.json").resolve()
    )
    assert config.adapters.enabled == ("generic", "enterprise-java")
    assert config.gaps.risk_patterns == ("@DS", "@Transactional", "@RocketMQMessageListener", "@XxlJob")


def test_create_default_config_writes_enterprise_java_profile_layout(tmp_path: Path) -> None:
    config_path = create_default_config(tmp_path, profile="enterprise-java")

    assert config_path == tmp_path / ".driftkb" / "config.yml"
    assert (tmp_path / ".agents" / "kb" / "zh" / "curated").is_dir()
    assert (tmp_path / ".agents" / "kb" / "zh" / "generated").is_dir()
    assert (tmp_path / ".agents" / "kb" / "zh" / "_validation").is_dir()
    assert (tmp_path / ".agents" / "kb" / "zh" / "_validation" / "fingerprints").is_dir()

    config_text = config_path.read_text(encoding="utf-8")
    assert "profile: enterprise-java" in config_text
    assert "curated_dir: .agents/kb/zh/curated" in config_text
    assert "cache_path: .agents/kb/zh/_validation/call_graph_cache.json" in config_text
    assert "kb_section_map_path: .agents/kb/zh/_validation/kb_section_map.json" in config_text
    assert "snapshot_dir: .agents/kb/zh/_validation/fingerprints" in config_text
    assert "    - enterprise-java" in config_text
    assert '    - "@RocketMQMessageListener"' in config_text


def test_create_default_config_does_not_overwrite_existing_file(tmp_path: Path) -> None:
    config_path = tmp_path / ".driftkb" / "config.yml"
    config_path.parent.mkdir()
    config_path.write_text("version: 1\nprofile: default\n", encoding="utf-8")

    assert create_default_config(tmp_path, profile="enterprise-java") == config_path

    assert config_path.read_text(encoding="utf-8") == "version: 1\nprofile: default\n"


def test_load_config_cli_profile_overrides_config_profile(tmp_path: Path) -> None:
    config_path = tmp_path / ".driftkb" / "config.yml"
    config_path.parent.mkdir()
    config_path.write_text(
        """
version: 1
profile: enterprise-java
""".lstrip(),
        encoding="utf-8",
    )

    config = load_config(tmp_path, profile="default")

    assert config.profile.name == "default"
    assert config.kb.curated_dir == (tmp_path / "docs" / "kb" / "curated").resolve()


def test_load_config_parses_empty_inline_list(tmp_path: Path) -> None:
    config_path = tmp_path / ".driftkb" / "config.yml"
    config_path.parent.mkdir()
    config_path.write_text(
        """
version: 1
gaps:
  risk_patterns: []
""".lstrip(),
        encoding="utf-8",
    )

    config = load_config(tmp_path)

    assert config.gaps.risk_patterns == ()


def test_load_config_rejects_quoted_boolean(tmp_path: Path) -> None:
    config_path = tmp_path / ".driftkb" / "config.yml"
    config_path.parent.mkdir()
    config_path.write_text(
        """
version: 1
verify:
  enabled: "false"
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="must be a boolean"):
        load_config(tmp_path)


def test_load_config_rejects_paths_outside_repo(tmp_path: Path) -> None:
    config_path = tmp_path / ".driftkb" / "config.yml"
    config_path.parent.mkdir()
    config_path.write_text(
        """
version: 1
validation:
  report_path: ../outside.json
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="must stay inside"):
        load_config(tmp_path)


def test_load_config_rejects_non_positive_timeout(tmp_path: Path) -> None:
    config_path = tmp_path / ".driftkb" / "config.yml"
    config_path.parent.mkdir()
    config_path.write_text(
        """
version: 1
verify:
  timeout_seconds: 0
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="greater than 0"):
        load_config(tmp_path)


def test_load_config_default_profile_rejects_enterprise_policy_alias(tmp_path: Path) -> None:
    config_path = tmp_path / ".driftkb" / "config.yml"
    config_path.parent.mkdir()
    config_path.write_text(
        """
version: 1
validation:
  default_stale_policy: fail_on_source_change
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="default_stale_policy"):
        load_config(tmp_path)


def test_load_config_rejects_unknown_profile(tmp_path: Path) -> None:
    config_path = tmp_path / ".driftkb" / "config.yml"
    config_path.parent.mkdir()
    config_path.write_text(
        """
version: 1
profile: typo
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="unknown profile"):
        load_config(tmp_path)
