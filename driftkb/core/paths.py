from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import Path


def to_posix_relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def normalize_posix_path(path: str | Path) -> str:
    return str(path).replace("\\", "/").strip().lstrip("./")


def path_matches_any(path: str | Path, patterns: tuple[str, ...] | list[str]) -> bool:
    normalized = normalize_posix_path(path)
    return any(glob_matches(normalized, pattern) for pattern in patterns)


def glob_matches(path: str, pattern: str) -> bool:
    normalized_pattern = normalize_posix_path(pattern)
    return _match_segments(
        normalize_posix_path(path).split("/"),
        normalized_pattern.split("/"),
    )


def _match_segments(path_segments: list[str], pattern_segments: list[str]) -> bool:
    if not pattern_segments:
        return not path_segments

    head = pattern_segments[0]
    tail = pattern_segments[1:]
    if head == "**":
        return any(_match_segments(path_segments[index:], tail) for index in range(len(path_segments) + 1))

    if not path_segments:
        return False
    return fnmatchcase(path_segments[0], head) and _match_segments(path_segments[1:], tail)


def repo_paths_relative_to_source_root(
    repo_relative_paths: tuple[str, ...],
    repo_root: Path,
    source_root: Path,
) -> tuple[str, ...]:
    normalized: list[str] = []
    resolved_source_root = source_root.resolve()
    for repo_path in repo_relative_paths:
        absolute = (repo_root / repo_path).resolve()
        try:
            normalized.append(absolute.relative_to(resolved_source_root).as_posix())
        except ValueError:
            continue
    return tuple(normalized)
