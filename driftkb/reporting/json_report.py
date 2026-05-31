from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from driftkb.core.models import ValidationIssue, ValidationResult, ValidationStatus
from driftkb.core.report import REPORT_SCHEMA_VERSION


def report_to_dict(report: ValidationResult) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "result": _status_value(report.result),
        "checked_at_commit": report.checked_at_commit,
        "stale": [_issue_to_dict(issue) for issue in report.stale],
        "warnings": [_issue_to_dict(issue) for issue in report.warnings],
        "verify": [_issue_to_dict(issue) for issue in report.verify],
        "gaps": [_issue_to_dict(issue) for issue in report.gaps],
        "metadata": report.metadata,
    }


def report_to_json(report: ValidationResult) -> str:
    return json.dumps(report_to_dict(report), indent=2, sort_keys=True)


def write_json_report(report: ValidationResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report_to_json(report) + "\n", encoding="utf-8")


def _issue_to_dict(issue: ValidationIssue) -> dict[str, Any]:
    return {
        "code": issue.code,
        "message": issue.message,
        "path": _path_to_string(issue.path),
        "severity": _status_value(issue.severity),
        "metadata": issue.metadata,
    }


def _status_value(status: ValidationStatus | str) -> str:
    return status.value if isinstance(status, ValidationStatus) else status


def _path_to_string(path: Path | None) -> str | None:
    if path is None:
        return None
    return path.as_posix()
