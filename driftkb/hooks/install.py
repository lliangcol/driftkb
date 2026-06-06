from __future__ import annotations

import os
import shlex
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


def install_hook(
    repo_root: Path,
    hook: str,
    *,
    force: bool = False,
    strict: bool = False,
    config: Path | None = None,
    profile: str | None = None,
    no_verify: bool = False,
    output_format: str = "text",
) -> HookInstallResult:
    if hook not in {"pre-commit", "pre-push"}:
        raise HookInstallError(f"unsupported hook: {hook}")

    repo_root = repo_root.resolve()
    hook_path = _git_path(repo_root, f"hooks/{hook}")
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    existed = hook_path.exists()
    if existed and not force:
        raise HookInstallError(f"{hook_path} already exists; rerun with --force to overwrite it")

    hook_path.write_text(
        _validate_hook_template(
            strict=strict,
            config=config,
            profile=profile,
            no_verify=no_verify,
            output_format=output_format,
        ),
        encoding="utf-8",
        newline="\n",
    )
    _make_executable(hook_path)
    return HookInstallResult(hook=hook, path=hook_path, overwritten=existed)


def _validate_hook_template(
    *,
    strict: bool,
    config: Path | None,
    profile: str | None,
    no_verify: bool,
    output_format: str,
) -> str:
    command = _validate_command(
        strict=strict,
        config=config,
        profile=profile,
        no_verify=no_verify,
        output_format=output_format,
    )
    return f"#!/bin/sh\nset -e\n{command}\n"


def _validate_command(
    *,
    strict: bool,
    config: Path | None,
    profile: str | None,
    no_verify: bool,
    output_format: str,
) -> str:
    args = ["driftkb", "validate"]
    if config is not None:
        args.extend(("--config", config.as_posix()))
    if profile is not None:
        args.extend(("--profile", profile))
    if no_verify:
        args.append("--no-verify")
    if output_format != "text":
        args.extend(("--format", output_format))
    if strict:
        args.append("--strict")
    return " ".join(shlex.quote(item) for item in args)


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
