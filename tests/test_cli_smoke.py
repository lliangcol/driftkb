from __future__ import annotations

from pathlib import Path

from driftkb import __version__
from driftkb.cli.main import main


def test_version_outputs_package_version(capsys) -> None:
    assert main(["version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


def test_init_creates_default_config_and_kb_dir(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["init"]) == 0

    assert (tmp_path / ".driftkb" / "config.yml").is_file()
    assert (tmp_path / "docs" / "kb" / "curated").is_dir()
    assert (tmp_path / "docs" / "kb" / "generated").is_dir()
    assert (tmp_path / ".driftkb" / "validation").is_dir()
    assert "created .driftkb/config.yml and docs/kb/curated/" in capsys.readouterr().out


def test_init_enterprise_java_profile_creates_profile_config_without_overwriting(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["init", "--profile", "enterprise-java"]) == 0

    config_path = tmp_path / ".driftkb" / "config.yml"
    assert config_path.is_file()
    config_text = config_path.read_text(encoding="utf-8")
    assert "profile: enterprise-java" in config_text
    assert "curated_dir: .agents/kb/zh/curated" in config_text
    assert "    - enterprise-java" in config_text
    assert (tmp_path / ".agents" / "kb" / "zh" / "curated").is_dir()
    assert "created .driftkb/config.yml and .agents/kb/zh/curated/" in capsys.readouterr().out

    config_path.write_text("version: 1\nprofile: default\n", encoding="utf-8")

    assert main(["init", "--profile", "enterprise-java"]) == 0

    assert config_path.read_text(encoding="utf-8") == "version: 1\nprofile: default\n"


def test_validate_empty_repo_warns_when_head_is_unavailable(tmp_path: Path, capsys) -> None:
    assert main(["validate", "--repo-root", str(tmp_path), "--no-write-report"]) == 0

    output = capsys.readouterr().out
    assert "DriftKB: WARN" in output
    assert "git failed to get HEAD commit" in output
