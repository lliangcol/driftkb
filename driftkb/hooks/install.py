from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


class HookInstallError(RuntimeError):
    """Raised when a repository hook cannot be installed."""


@dataclass(frozen=True)
class HookInstallResult:
    hook: str
    path: Path
    overwritten: bool = False


def install_hook(repo_root: Path, hook: str, *, force: bool = False, strict: bool = False) -> HookInstallResult:
    if hook != "pre-push":
        raise HookInstallError(f"unsupported hook: {hook}")

    repo_root = repo_root.resolve()
    hook_path = _git_path(repo_root, f"hooks/{hook}")
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    existed = hook_path.exists()
    if existed and not force:
        raise HookInstallError(f"{hook_path} already exists; rerun with --force to overwrite it")

    hook_path.write_text(_pre_push_template(strict=strict), encoding="utf-8", newline="\n")
    _make_executable(hook_path)
    return HookInstallResult(hook=hook, path=hook_path, overwritten=existed)


def _pre_push_template(*, strict: bool) -> str:
    command = "driftkb validate --strict" if strict else "driftkb validate"
    return f"#!/bin/sh\nset -e\n{command}\n"


def _make_executable(path: Path) -> None:
    if os.name == "nt":
        return
    mode = path.stat().st_mode
    path.chmod(mode | 0o111)


def _git_path(repo_root: Path, path: str) -> Path:
    try:
        process = subprocess.run(
            ["git", "rev-parse", "--git-path", path],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise HookInstallError(f"failed to run git: {exc}") from exc
    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip() or f"exit code {process.returncode}"
        raise HookInstallError(f"{repo_root} does not look like a git repository: {detail}")
    raw_path = Path(process.stdout.strip())
    return raw_path.resolve() if raw_path.is_absolute() else (repo_root / raw_path).resolve()
