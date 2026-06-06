from __future__ import annotations

import subprocess
from pathlib import Path

from driftkb.cli.main import main


def test_hooks_install_pre_push_writes_default_hook(tmp_path: Path, capsys) -> None:
    _git(tmp_path, "init")

    exit_code = main(["hooks", "install", "pre-push", "--repo-root", str(tmp_path)])

    hook_path = tmp_path / ".git" / "hooks" / "pre-push"
    assert exit_code == 0
    assert hook_path.read_text(encoding="utf-8") == "#!/bin/sh\nset -e\ndriftkb validate\n"
    assert f"installed pre-push at {hook_path}" in capsys.readouterr().out


def test_hooks_install_pre_push_refuses_to_overwrite_existing_hook(tmp_path: Path, capsys) -> None:
    _git(tmp_path, "init")
    hook_path = tmp_path / ".git" / "hooks" / "pre-push"
    hook_path.write_text("#!/bin/sh\necho existing\n", encoding="utf-8")

    exit_code = main(["hooks", "install", "pre-push", "--repo-root", str(tmp_path)])

    assert exit_code == 2
    assert hook_path.read_text(encoding="utf-8") == "#!/bin/sh\necho existing\n"
    output = capsys.readouterr().out
    assert "already exists" in output
    assert "--force" in output


def test_hooks_install_pre_push_force_strict_overwrites_existing_hook(tmp_path: Path, capsys) -> None:
    _git(tmp_path, "init")
    hook_path = tmp_path / ".git" / "hooks" / "pre-push"
    hook_path.write_text("#!/bin/sh\necho existing\n", encoding="utf-8")

    exit_code = main(
        [
            "hooks",
            "install",
            "pre-push",
            "--repo-root",
            str(tmp_path),
            "--force",
            "--strict",
        ]
    )

    assert exit_code == 0
    assert hook_path.read_text(encoding="utf-8") == "#!/bin/sh\nset -e\ndriftkb validate --strict\n"
    assert f"overwrote pre-push at {hook_path}" in capsys.readouterr().out


def test_hooks_install_pre_commit_supports_validate_options(tmp_path: Path, capsys) -> None:
    _git(tmp_path, "init")

    exit_code = main(
        [
            "hooks",
            "install",
            "pre-commit",
            "--repo-root",
            str(tmp_path),
            "--config",
            ".driftkb/custom.yml",
            "--profile",
            "enterprise-java",
            "--no-verify",
            "--format",
            "json",
            "--strict",
        ]
    )

    hook_path = tmp_path / ".git" / "hooks" / "pre-commit"
    assert exit_code == 0
    assert hook_path.read_text(encoding="utf-8") == (
        "#!/bin/sh\n"
        "set -e\n"
        "driftkb validate --config .driftkb/custom.yml --profile enterprise-java --no-verify --format json --strict\n"
    )
    assert f"installed pre-commit at {hook_path}" in capsys.readouterr().out


def test_hooks_install_pre_push_supports_linked_worktree(tmp_path: Path, capsys) -> None:
    main_repo = tmp_path / "main"
    worktree = tmp_path / "linked"
    main_repo.mkdir()
    _git(main_repo, "init")
    _git(main_repo, "config", "user.name", "DriftKB Tests")
    _git(main_repo, "config", "user.email", "tests@example.invalid")
    (main_repo / "README.md").write_text("# Main\n", encoding="utf-8")
    _git(main_repo, "add", ".")
    _git(main_repo, "commit", "-m", "baseline")
    _git(main_repo, "worktree", "add", str(worktree))

    exit_code = main(["hooks", "install", "pre-push", "--repo-root", str(worktree)])

    hook_path = _git_path(worktree, "hooks/pre-push")
    assert exit_code == 0
    assert hook_path.read_text(encoding="utf-8") == "#!/bin/sh\nset -e\ndriftkb validate\n"
    assert f"installed pre-push at {hook_path}" in capsys.readouterr().out


def _git(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=path, text=True, capture_output=True, check=True)


def _git_path(path: Path, git_path: str) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--git-path", git_path],
        cwd=path,
        text=True,
        capture_output=True,
        check=True,
    )
    raw = Path(result.stdout.strip())
    return raw.resolve() if raw.is_absolute() else (path / raw).resolve()
