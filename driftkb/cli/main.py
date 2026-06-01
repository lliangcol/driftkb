from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from driftkb import __version__
from driftkb.core.config import (
    DEFAULT_CONFIG_PATH,
    ConfigError,
    create_default_config,
    load_config,
)
from driftkb.core.frontmatter import FrontmatterError
from driftkb.core.models import ValidationIssue, ValidationResult, ValidationStatus
from driftkb.core.validate import apply_validate_overrides, load_kb_file, scan_curated_kb_files, validate_kb
from driftkb.fingerprints.update import update_fingerprints
from driftkb.gaps.detect import detect_gaps, result_to_json
from driftkb.hooks.install import HookInstallError, install_hook
from driftkb.profiles import available_profiles
from driftkb.promote import PromoteError, promote_generated_stub
from driftkb.reporting.json_report import report_to_json, write_json_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="driftkb",
        description="Keep Markdown knowledge bases honest when code changes.",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("version", help="Print the DriftKB version.")
    init_parser = subparsers.add_parser("init", help="Create the default DriftKB config and KB directory.")
    init_parser.add_argument("--profile", choices=available_profiles(), help="Profile config to create.")
    validate_parser = subparsers.add_parser("validate", help="Validate KB freshness and verification rules.")
    validate_parser.add_argument(
        "--repo-root", type=Path, default=Path("."), help="Repository root. Defaults to current directory."
    )
    validate_parser.add_argument("--config", type=Path, help="Path to DriftKB config. Defaults to .driftkb/config.yml.")
    validate_parser.add_argument(
        "--profile", choices=available_profiles(), help="Profile to apply. Overrides config profile."
    )
    validate_parser.add_argument("--kb-dir", type=Path, help="Override curated KB directory.")
    validate_parser.add_argument("--source-root", type=Path, help="Override source root for source_globs matching.")
    validate_parser.add_argument("--report", type=Path, help="Override JSON report path.")
    validate_parser.add_argument("--no-write-report", action="store_true", help="Do not write a JSON report.")
    validate_parser.add_argument("--no-verify", action="store_true", help="Do not run Markdown verify blocks.")
    validate_parser.add_argument(
        "--verify-timeout",
        type=float,
        default=None,
        metavar="SECONDS",
        help="Timeout per verify block command. Defaults to 10 seconds.",
    )
    validate_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    validate_parser.add_argument("--strict", action="store_true", help="Return exit code 1 for WARN as well as FAIL.")

    promote_parser = subparsers.add_parser("promote", help="Promote a generated KB stub after human review.")
    promote_parser.add_argument("path", type=Path, help="Generated KB stub path, for example docs/kb/generated/foo.md.")
    promote_parser.add_argument(
        "--repo-root", type=Path, default=Path("."), help="Repository root. Defaults to current directory."
    )
    promote_parser.add_argument("--config", type=Path, help="Path to DriftKB config. Defaults to .driftkb/config.yml.")
    promote_parser.add_argument(
        "--profile", choices=available_profiles(), help="Profile to apply. Overrides config profile."
    )
    promote_parser.add_argument(
        "--stale-policy", choices=["warn", "fail"], default="fail", help="Stale policy for the curated KB."
    )
    promote_parser.add_argument(
        "--update-fingerprints", action="store_true", help="Update fingerprint snapshots after promotion."
    )
    promote_parser.add_argument("--dry-run", action="store_true", help="Show the promotion without moving files.")

    gaps_parser = subparsers.add_parser("gaps", help="Gap detection commands.")
    gaps_subparsers = gaps_parser.add_subparsers(dest="gaps_command")
    gaps_detect_parser = gaps_subparsers.add_parser("detect", help="Detect missing KB coverage candidates.")
    gaps_detect_parser.add_argument(
        "--repo-root", type=Path, default=Path("."), help="Repository root. Defaults to current directory."
    )
    gaps_detect_parser.add_argument(
        "--config", type=Path, help="Path to DriftKB config. Defaults to .driftkb/config.yml."
    )
    gaps_detect_parser.add_argument(
        "--profile", choices=available_profiles(), help="Profile to apply. Overrides config profile."
    )
    gaps_detect_parser.add_argument("--write", action="store_true", help="Write generated KB stubs.")
    gaps_detect_parser.add_argument(
        "--dry-run", action="store_true", help="Do not write generated KB stubs. This is the default."
    )
    gaps_detect_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    gaps_detect_parser.add_argument("--risk", choices=["high", "all"], default="high", help="Candidate risk filter.")

    graph_parser = subparsers.add_parser("graph", help="Call graph cache helper commands.")
    graph_subparsers = graph_parser.add_subparsers(dest="graph_command")
    graph_anchors_parser = graph_subparsers.add_parser("anchors", help="Print curated KB anchor_symbols as JSON.")
    graph_anchors_parser.add_argument(
        "--repo-root", type=Path, default=Path("."), help="Repository root. Defaults to current directory."
    )
    graph_anchors_parser.add_argument(
        "--config", type=Path, help="Path to DriftKB config. Defaults to .driftkb/config.yml."
    )
    graph_anchors_parser.add_argument(
        "--profile", choices=available_profiles(), help="Profile to apply. Overrides config profile."
    )
    graph_anchors_parser.add_argument("--kb-dir", type=Path, help="Override curated KB directory.")

    fingerprints_parser = subparsers.add_parser("fingerprints", help="Fingerprint snapshot commands.")
    fingerprints_subparsers = fingerprints_parser.add_subparsers(dest="fingerprints_command")
    fingerprints_update_parser = fingerprints_subparsers.add_parser("update", help="Update fingerprint snapshots.")
    fingerprints_update_parser.add_argument(
        "--repo-root", type=Path, default=Path("."), help="Repository root. Defaults to current directory."
    )
    fingerprints_update_parser.add_argument(
        "--config", type=Path, help="Path to DriftKB config. Defaults to .driftkb/config.yml."
    )
    fingerprints_update_parser.add_argument(
        "--profile", choices=available_profiles(), help="Profile to apply. Overrides config profile."
    )
    fingerprints_update_parser.add_argument("--kb-file", type=Path, help="Update snapshots for one curated KB file.")
    fingerprints_update_parser.add_argument(
        "--all", action="store_true", help="Update snapshots for all curated KB files."
    )

    hooks_parser = subparsers.add_parser("hooks", help="Hook management commands.")
    hooks_subparsers = hooks_parser.add_subparsers(dest="hooks_command")
    hooks_install_parser = hooks_subparsers.add_parser("install", help="Install repository hooks.")
    hooks_install_parser.add_argument("hook", choices=["pre-push"], help="Hook to install.")
    hooks_install_parser.add_argument(
        "--repo-root", type=Path, default=Path("."), help="Repository root. Defaults to current directory."
    )
    hooks_install_parser.add_argument("--force", action="store_true", help="Overwrite an existing hook.")
    hooks_install_parser.add_argument(
        "--strict", action="store_true", help="Install a hook that fails on WARN as well as FAIL."
    )

    return parser


def init_project(root: Path, profile: str | None = None) -> None:
    create_default_config(root, profile=profile)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "version":
        print(__version__)
        return 0

    if args.command == "init":
        init_project(Path.cwd(), profile=args.profile)
        config = load_config(Path.cwd(), profile=args.profile)
        print(f"created {DEFAULT_CONFIG_PATH.as_posix()} and {_display_path(config.kb.curated_dir, config.repo_root)}/")
        return 0

    if args.command == "validate":
        return run_validate(args)

    if args.command == "promote":
        return run_promote(args)

    if args.command == "gaps" and args.gaps_command == "detect":
        return run_gaps_detect(args)

    if args.command == "graph" and args.graph_command == "anchors":
        return run_graph_anchors(args)

    if args.command == "fingerprints" and args.fingerprints_command == "update":
        return run_fingerprints_update(args)

    if args.command == "hooks" and args.hooks_command == "install":
        return run_hooks_install(args)

    parser.print_help()
    return 2


app = main


def run_validate(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.repo_root, args.config, profile=args.profile)
        config = apply_validate_overrides(
            config,
            kb_dir=args.kb_dir,
            source_root=args.source_root,
            report_path=args.report,
            verify_enabled=False if args.no_verify else None,
            verify_timeout_seconds=args.verify_timeout,
        )
        report = validate_kb(config)
        if not args.no_write_report:
            write_json_report(report, config.validation.report_path)
    except ConfigError as exc:
        print(f"DriftKB: ERROR\nreason: {exc}")
        return 2
    except (OSError, ValueError) as exc:
        print(f"DriftKB: ERROR\nreason: {exc}")
        return 2

    if args.format == "json":
        print(report_to_json(report))
    else:
        print(format_text_report(report))

    if report.result == ValidationStatus.FAIL:
        return 1
    if args.strict and report.result == ValidationStatus.WARN:
        return 1
    return 0


def run_hooks_install(args: argparse.Namespace) -> int:
    try:
        result = install_hook(args.repo_root, args.hook, force=args.force, strict=args.strict)
    except HookInstallError as exc:
        print(f"DriftKB: ERROR\nreason: {exc}")
        return 2

    action = "overwrote" if result.overwritten else "installed"
    print(f"DriftKB hooks: {action} {result.hook} at {result.path}")
    return 0


def run_fingerprints_update(args: argparse.Namespace) -> int:
    if not args.all and args.kb_file is None:
        print("DriftKB: ERROR\nreason: fingerprints update requires --all or --kb-file")
        return 2
    if args.all and args.kb_file is not None:
        print("DriftKB: ERROR\nreason: use either --all or --kb-file, not both")
        return 2
    try:
        config = load_config(args.repo_root, args.config, profile=args.profile)
        result = update_fingerprints(config, kb_file=args.kb_file, all_kb=args.all)
    except (ConfigError, OSError, ValueError) as exc:
        print(f"DriftKB: ERROR\nreason: {exc}")
        return 2
    print(f"updated {result.updated} fingerprint snapshot(s)")
    if result.skipped:
        print(f"skipped {result.skipped} file(s)")
    return 0


def run_promote(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.repo_root, args.config, profile=args.profile)
        result = promote_generated_stub(
            config,
            args.path,
            stale_policy=args.stale_policy,
            update_fingerprints_after=args.update_fingerprints,
            dry_run=args.dry_run,
        )
    except (ConfigError, FrontmatterError, PromoteError, OSError, ValueError) as exc:
        print(f"DriftKB: ERROR\nreason: {exc}")
        return 2

    print(format_promote_report(result, config.repo_root))
    return 0


def run_gaps_detect(args: argparse.Namespace) -> int:
    if args.write and args.dry_run:
        print("DriftKB: ERROR\nreason: use either --write or --dry-run, not both")
        return 2
    try:
        config = load_config(args.repo_root, args.config, profile=args.profile)
        result = detect_gaps(config, write=args.write, risk_filter=args.risk)
    except (ConfigError, OSError, ValueError) as exc:
        print(f"DriftKB: ERROR\nreason: {exc}")
        return 2

    if args.format == "json":
        print(result_to_json(result, config.repo_root))
    else:
        print(format_gap_report(result, config.repo_root, write=args.write))
    return 0


def run_graph_anchors(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.repo_root, args.config, profile=args.profile)
        config = apply_validate_overrides(config, kb_dir=args.kb_dir)
        anchors: dict[str, None] = {}
        for kb_path in scan_curated_kb_files(config.kb.curated_dir):
            kb_file = load_kb_file(kb_path, config)
            for symbol in kb_file.anchor_symbols:
                anchors.setdefault(symbol, None)
    except (ConfigError, FrontmatterError, OSError) as exc:
        print(f"DriftKB: ERROR\nreason: {exc}")
        return 2
    print(json.dumps(sorted(anchors), indent=2))
    return 0


def format_text_report(report: ValidationResult) -> str:
    lines = [
        f"DriftKB: {report.result.value}",
        f"checked_at_commit: {report.checked_at_commit or 'unknown'}",
        f"stale: {len(report.stale)}",
        f"warnings: {len(report.warnings)}",
        f"verify: {len(report.verify)}",
    ]
    for issue in (*report.stale, *report.warnings, *_visible_verify_issues(report)):
        lines.extend(_format_issue(issue))
    return "\n".join(lines)


def format_promote_report(result, repo_root: Path) -> str:
    mode = "dry-run" if result.dry_run else "write"
    lines = [
        "DriftKB promote: PASS",
        f"mode: {mode}",
        f"source: {_display_path(result.source_path, repo_root)}",
        f"target: {_display_path(result.target_path, repo_root)}",
        f"last_verified_commit: {result.head_commit}",
        f"stale_policy: {result.stale_policy}",
    ]
    if result.fingerprint_update is not None:
        lines.append(f"fingerprints_updated: {result.fingerprint_update.updated}")
        lines.append(f"fingerprints_skipped: {result.fingerprint_update.skipped}")
    return "\n".join(lines)


def format_gap_report(result, repo_root: Path, *, write: bool) -> str:
    if not result.enabled:
        return "DriftKB gaps: disabled"

    lines = [
        "DriftKB gaps: PASS" if not result.gaps else "DriftKB gaps: WARN",
        f"checked_at_commit: {result.checked_at_commit or 'unknown'}",
        f"mode: {'write' if write else 'dry-run'}",
        f"gaps: {len(result.gaps)}",
        f"written: {len(result.written)}",
        f"skipped_whitelisted: {len(result.skipped_whitelisted)}",
    ]
    for warning in result.warnings:
        lines.extend(("", f"WARN {warning}"))
    for gap in result.gaps:
        lines.extend(
            (
                "",
                f"WARN {gap.candidate.symbol}",
                f"  risk: {gap.candidate.risk}",
                f"  source: {gap.candidate.file}",
                f"  adapter: {gap.candidate.adapter}",
                f"  output_path: {_display_path(gap.output_path, repo_root)}",
            )
        )
    return "\n".join(lines)


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _format_issue(issue: ValidationIssue) -> list[str]:
    path = issue.path.as_posix() if issue.path is not None else "<repo>"
    lines = ["", f"{issue.severity.value} {path}", f"  reason: {issue.message}"]
    matched_paths = issue.metadata.get("matched_paths")
    if matched_paths:
        lines.append("  matched_paths:")
        for matched_path in matched_paths:
            lines.append(f"    - {matched_path}")
    if issue.code.startswith("verify_block_"):
        lines.append(f"  block_index: {issue.metadata.get('block_index')}")
        command = issue.metadata.get("command")
        if command:
            lines.append(f"  command: {command}")
        expected = issue.metadata.get("expected")
        if expected:
            lines.append(f"  expected: {expected}")
        actual = issue.metadata.get("actual_match_count")
        if actual is not None:
            lines.append(f"  actual_match_count: {actual}")
    return lines


def _visible_verify_issues(report: ValidationResult) -> tuple[ValidationIssue, ...]:
    return tuple(issue for issue in report.verify if issue.severity != ValidationStatus.PASS)


if __name__ == "__main__":
    raise SystemExit(main())
