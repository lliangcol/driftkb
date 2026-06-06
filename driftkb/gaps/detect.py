from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from driftkb.adapters.base import Fingerprint
from driftkb.adapters.registry import build_adapters
from driftkb.core.config import DriftKBConfig
from driftkb.core.frontmatter import FrontmatterError
from driftkb.core.git import GitError, get_head_commit
from driftkb.core.paths import glob_matches
from driftkb.core.validate import all_source_files, load_kb_file, scan_curated_kb_files

RiskFilter = Literal["high", "all"]


@dataclass(frozen=True)
class GapCandidate:
    symbol: str
    file: str
    adapter: str
    annotations: tuple[str, ...]
    risk: str


@dataclass(frozen=True)
class Gap:
    candidate: GapCandidate
    output_path: Path
    topic: str


@dataclass(frozen=True)
class GapDetectionResult:
    enabled: bool
    checked_at_commit: str | None
    gaps: tuple[Gap, ...]
    written: tuple[Path, ...]
    skipped_whitelisted: tuple[GapCandidate, ...]
    warnings: tuple[str, ...] = ()
    scanned_files: int = 0
    candidates: int = 0
    covered: int = 0
    filtered_low_risk: int = 0


def detect_gaps(config: DriftKBConfig, *, write: bool = False, risk_filter: RiskFilter = "high") -> GapDetectionResult:
    if not config.gaps.enabled:
        return GapDetectionResult(
            enabled=False,
            checked_at_commit=_head_or_none(config),
            gaps=(),
            written=(),
            skipped_whitelisted=(),
        )

    warnings: list[str] = []
    checked_at_commit = _head_or_none(config)
    if checked_at_commit is None:
        warnings.append("git failed to get HEAD commit; generated_from_commit will be unknown")

    anchors = _curated_anchor_symbols(config, warnings)
    anchors.update(_section_map_anchor_symbols(config, warnings))
    whitelist = load_gap_whitelist(config.gaps.whitelist_path)

    scan = _scan_candidates(config, warnings)
    candidates = scan.candidates
    gaps: list[Gap] = []
    skipped_whitelisted: list[GapCandidate] = []
    used_output_paths: set[Path] = set()
    covered = 0
    filtered_low_risk = 0

    for candidate in candidates:
        if risk_filter == "high" and candidate.risk != "high":
            filtered_low_risk += 1
            continue
        if candidate.symbol in anchors:
            covered += 1
            continue
        if _is_whitelisted(candidate.symbol, whitelist):
            skipped_whitelisted.append(candidate)
            continue
        topic, output_path = _output_for_candidate(config, candidate, used_output_paths)
        used_output_paths.add(output_path)
        gaps.append(
            Gap(
                candidate=candidate,
                output_path=output_path,
                topic=topic,
            )
        )

    written: list[Path] = []
    if write:
        config.kb.generated_dir.mkdir(parents=True, exist_ok=True)
        for gap in gaps:
            if gap.output_path.exists():
                warnings.append(f"skipped existing generated stub: {_report_path(gap.output_path, config.repo_root)}")
                continue
            gap.output_path.write_text(
                render_generated_stub(
                    gap,
                    checked_at_commit or "unknown",
                    anchor_field=config.profile.generated_anchor_field,
                    review_status_field=config.profile.generated_review_status_field,
                    pending_status=config.profile.generated_pending_review_status,
                ),
                encoding="utf-8",
            )
            written.append(gap.output_path)

    return GapDetectionResult(
        enabled=True,
        checked_at_commit=checked_at_commit,
        gaps=tuple(gaps),
        written=tuple(written),
        skipped_whitelisted=tuple(skipped_whitelisted),
        warnings=tuple(warnings),
        scanned_files=scan.scanned_files,
        candidates=len(candidates),
        covered=covered,
        filtered_low_risk=filtered_low_risk,
    )


def load_gap_whitelist(path: Path) -> tuple[str, ...]:
    if not path.exists():
        return ()
    patterns: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        patterns.append(stripped)
    return tuple(patterns)


def render_generated_stub(
    gap: Gap,
    generated_from_commit: str,
    *,
    anchor_field: str = "anchor_symbols",
    review_status_field: str = "validation_status",
    pending_status: str = "pending_human_review",
) -> str:
    candidate = gap.candidate
    annotations = tuple(_display_annotation(annotation) for annotation in candidate.annotations)
    lines = [
        "---",
        "kind: generated",
        f"topic: {gap.topic}",
        f"risk: {candidate.risk}",
        f"generated_from_commit: {generated_from_commit}",
        "generator: driftkb gaps detect",
        f"{review_status_field}: {pending_status}",
        "source_globs:",
        f'  - "{candidate.file}"',
        f"{anchor_field}:",
        f"  - {candidate.symbol}",
        "---",
        "",
        "<!-- Auto-generated stub. Human review required before promotion. -->",
        "",
        f"# [Needs review] {candidate.symbol}",
        "",
        "## Why this was generated",
        "",
        "DriftKB found a high-risk source symbol without curated KB coverage.",
        "",
        "## Extracted signals",
        "",
        f"- adapter: {candidate.adapter}",
        "- annotations:",
    ]
    if annotations:
        lines.extend(f"  - {annotation}" for annotation in annotations)
    else:
        lines.append("  - none")
    lines.extend(
        [
            "",
            "## To complete",
            "",
            "- Business rules",
            "- Integration contracts",
            "- Failure modes",
            "- Recommended verify blocks",
            "",
        ]
    )
    return "\n".join(lines)


def result_to_json(result: GapDetectionResult, repo_root: Path) -> str:
    payload: dict[str, Any] = {
        "enabled": result.enabled,
        "checked_at_commit": result.checked_at_commit,
        "summary": {
            "scanned_files": result.scanned_files,
            "candidates": result.candidates,
            "covered": result.covered,
            "filtered_low_risk": result.filtered_low_risk,
            "gaps": len(result.gaps),
            "written": len(result.written),
            "skipped_whitelisted": len(result.skipped_whitelisted),
        },
        "gaps": [
            {
                "symbol": gap.candidate.symbol,
                "risk": gap.candidate.risk,
                "adapter": gap.candidate.adapter,
                "file": gap.candidate.file,
                "annotations": list(gap.candidate.annotations),
                "output_path": _report_path(gap.output_path, repo_root),
            }
            for gap in result.gaps
        ],
        "written": [_report_path(path, repo_root) for path in result.written],
        "skipped_whitelisted": [candidate.symbol for candidate in result.skipped_whitelisted],
        "warnings": list(result.warnings),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


@dataclass(frozen=True)
class CandidateScan:
    candidates: tuple[GapCandidate, ...]
    scanned_files: int


def _scan_candidates(config: DriftKBConfig, warnings: list[str]) -> CandidateScan:
    adapters = build_adapters(config.adapters.enabled)
    by_symbol: dict[str, GapCandidate] = {}
    scanned_files = 0

    for source_path in all_source_files(config):
        absolute = config.sources.root / source_path
        adapter = next((item for item in adapters if item.supports(absolute)), None)
        if adapter is None:
            continue
        scanned_files += 1
        try:
            fingerprint = adapter.extract(absolute, config.sources.root)
        except (OSError, UnicodeError, ValueError) as exc:
            warnings.append(f"skipped {source_path}: {exc}")
            continue
        for candidate in _candidates_from_fingerprint(fingerprint, config.gaps.risk_patterns):
            by_symbol.setdefault(candidate.symbol, candidate)

    return CandidateScan(
        candidates=tuple(by_symbol[symbol] for symbol in sorted(by_symbol)),
        scanned_files=scanned_files,
    )


def _candidates_from_fingerprint(fingerprint: Fingerprint, risk_patterns: tuple[str, ...]) -> tuple[GapCandidate, ...]:
    symbols = _candidate_symbols(fingerprint)
    if not symbols:
        return ()
    risk = "high" if _has_risk_annotation(fingerprint.annotations, risk_patterns) else "low"
    return tuple(
        GapCandidate(
            symbol=symbol,
            file=fingerprint.file,
            adapter=fingerprint.adapter,
            annotations=fingerprint.annotations,
            risk=risk,
        )
        for symbol in symbols
    )


def _candidate_symbols(fingerprint: Fingerprint) -> tuple[str, ...]:
    fqcn = fingerprint.metadata.get("fqcn")
    if isinstance(fqcn, tuple) and all(isinstance(item, str) for item in fqcn):
        return fqcn
    if isinstance(fqcn, list) and all(isinstance(item, str) for item in fqcn):
        return tuple(fqcn)
    return fingerprint.symbols


def _curated_anchor_symbols(config: DriftKBConfig, warnings: list[str]) -> set[str]:
    anchors: set[str] = set()
    for kb_path in scan_curated_kb_files(config.kb.curated_dir):
        try:
            kb_file = load_kb_file(kb_path, config)
        except FrontmatterError as exc:
            warnings.append(f"skipped curated KB {kb_path}: {exc}")
            continue
        anchors.update(kb_file.anchor_symbols)
    return anchors


def _section_map_anchor_symbols(config: DriftKBConfig, warnings: list[str]) -> set[str]:
    path = config.graph.kb_section_map_path
    if path is None or not path.exists():
        return set()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        warnings.append(f"skipped kb_section_map.json: {exc}")
        return set()

    anchors = _anchors_from_section_map(raw)
    if anchors is None:
        warnings.append("skipped kb_section_map.json: unsupported schema")
        return set()
    return anchors


def _anchors_from_section_map(raw: Any) -> set[str] | None:
    if not isinstance(raw, dict):
        return None

    anchors: set[str] = set()
    for key in ("anchor_symbols", "anchor_classes"):
        value = raw.get(key)
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            anchors.update(value)

    sections = raw.get("sections", raw.get("kb_sections"))
    if isinstance(sections, dict):
        section_values = sections.values()
    elif isinstance(sections, list):
        section_values = sections
    else:
        section_values = ()

    for section in section_values:
        if not isinstance(section, dict):
            return None
        for key in ("anchor_symbols", "anchor_classes", "symbols", "classes"):
            value = section.get(key)
            if isinstance(value, list) and all(isinstance(item, str) for item in value):
                anchors.update(value)
        symbol = section.get("symbol")
        if isinstance(symbol, str):
            anchors.add(symbol)

    symbols = raw.get("symbols")
    if isinstance(symbols, dict):
        anchors.update(key for key in symbols if isinstance(key, str))
    elif isinstance(symbols, list) and all(isinstance(item, str) for item in symbols):
        anchors.update(symbols)

    return anchors


def _has_risk_annotation(annotations: tuple[str, ...], risk_patterns: tuple[str, ...]) -> bool:
    for annotation in annotations:
        normalized_annotation = _annotation_name(annotation)
        for pattern in risk_patterns:
            if annotation == pattern or normalized_annotation == _annotation_name(pattern):
                return True
    return False


def _annotation_name(annotation: str) -> str:
    return annotation.strip().removeprefix("@").split("(", 1)[0]


def _display_annotation(annotation: str) -> str:
    return _annotation_name(annotation)


def _is_whitelisted(symbol: str, whitelist: tuple[str, ...]) -> bool:
    return any(symbol == pattern or glob_matches(symbol, pattern) for pattern in whitelist)


def _topic_for_symbol(symbol: str) -> str:
    short_name = symbol.rsplit(".", 1)[-1]
    slug = re.sub(r"(?<!^)(?=[A-Z])", "-", short_name).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return f"{slug or 'symbol'}-stub"


def _output_for_candidate(
    config: DriftKBConfig,
    candidate: GapCandidate,
    used_output_paths: set[Path],
) -> tuple[str, Path]:
    base_topic = _topic_for_symbol(candidate.symbol)
    topic = base_topic
    output_path = config.kb.generated_dir / f"{topic}.md"
    if output_path in used_output_paths or output_path.exists():
        suffix = hashlib.sha256(candidate.symbol.encode("utf-8")).hexdigest()[:8]
        topic = f"{base_topic}-{suffix}"
        output_path = config.kb.generated_dir / f"{topic}.md"

    index = 2
    while output_path in used_output_paths or output_path.exists():
        topic = f"{base_topic}-{suffix}-{index}"
        output_path = config.kb.generated_dir / f"{topic}.md"
        index += 1
    return topic, output_path


def _head_or_none(config: DriftKBConfig) -> str | None:
    try:
        return get_head_commit(config.repo_root)
    except GitError:
        return None


def _report_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()
