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


def test_validate_empty_repo_warns_when_head_is_unavailable(tmp_path: Path, capsys) -> None:
    assert main(["validate", "--repo-root", str(tmp_path), "--no-write-report"]) == 0

    output = capsys.readouterr().out
    assert "DriftKB: WARN" in output
    assert "git failed to get HEAD commit" in output
