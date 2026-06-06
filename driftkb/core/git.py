from __future__ import annotations

import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


class GitError(RuntimeError):
    """Raised when a git command needed by DriftKB fails."""


_FIXED_COMMIT_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")


@dataclass(frozen=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


def run_git(args: Sequence[str], cwd: Path) -> CommandResult:
    try:
        process = subprocess.run(
            ["git", *args],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise GitError(f"failed to run git: {exc}") from exc
    return CommandResult(
        args=("git", *args),
        returncode=process.returncode,
        stdout=process.stdout,
        stderr=process.stderr,
    )


def get_head_commit(repo_root: Path) -> str:
    result = run_git(["rev-parse", "HEAD"], repo_root)
    if result.returncode != 0:
        raise GitError(_format_git_error("get HEAD commit", result))
    return result.stdout.strip()


def is_fixed_commit_ref(value: str) -> bool:
    return bool(_FIXED_COMMIT_RE.fullmatch(value.strip()))


def resolve_commit(repo_root: Path, commit: str) -> str:
    result = run_git(["rev-parse", "--verify", f"{commit}^{{commit}}"], repo_root)
    if result.returncode != 0:
        raise GitError(_format_git_error(f"resolve commit {commit}", result))
    return result.stdout.strip()


def commit_exists(repo_root: Path, commit: str) -> bool:
    result = run_git(["cat-file", "-e", f"{commit}^{{commit}}"], repo_root)
    return result.returncode == 0


def get_changed_files(
    repo_root: Path,
    base_commit: str,
    head: str = "HEAD",
    *,
    include_worktree: bool = False,
) -> tuple[str, ...]:
    result = run_git(
        ["diff", "--name-only", "--relative", "--diff-filter=ACDMRT", base_commit, head, "--"],
        repo_root,
    )
    if result.returncode != 0:
        raise GitError(_format_git_error(f"diff {base_commit}..{head}", result))
    paths = _split_git_paths(result.stdout)

    if include_worktree:
        worktree = run_git(["diff", "--name-only", "--relative", "--diff-filter=ACDMRT", head, "--"], repo_root)
        if worktree.returncode != 0:
            raise GitError(_format_git_error(f"diff {head}..working tree", worktree))
        paths.extend(_split_git_paths(worktree.stdout))

        untracked = run_git(["ls-files", "--others", "--exclude-standard"], repo_root)
        if untracked.returncode != 0:
            raise GitError(_format_git_error("list untracked files", untracked))
        paths.extend(_split_git_paths(untracked.stdout))

    return tuple(sorted(set(paths)))


def has_staged_changes(repo_root: Path) -> bool:
    result = run_git(["diff", "--cached", "--quiet", "--"], repo_root)
    if result.returncode == 0:
        return False
    if result.returncode == 1:
        return True
    raise GitError(_format_git_error("check staged changes", result))


def _split_git_paths(stdout: str) -> list[str]:
    return [line.strip().replace("\\", "/") for line in stdout.splitlines() if line.strip()]


def _format_git_error(action: str, result: CommandResult) -> str:
    detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
    return f"git failed to {action}: {detail}"
