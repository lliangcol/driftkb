from __future__ import annotations

import json
from pathlib import Path

from driftkb.core.models import ValidationIssue, ValidationResult, ValidationStatus
from driftkb.core.report import empty_pass_report
from driftkb.reporting.json_report import report_to_dict, report_to_json


def test_empty_pass_report_matches_schema_shape() -> None:
    report = empty_pass_report(checked_at_commit="abc123")

    assert report_to_dict(report) == {
        "schema_version": 1,
        "result": "PASS",
        "checked_at_commit": "abc123",
        "stale": [],
        "warnings": [],
        "verify": [],
        "gaps": [],
        "metadata": {},
    }


def test_report_to_json_serializes_issues() -> None:
    report = ValidationResult(
        result=ValidationStatus.WARN,
        checked_at_commit="def456",
        warnings=(
            ValidationIssue(
                code="stale_policy",
                message="KB may be stale.",
                path=Path("docs/kb/curated/payment.md"),
                severity=ValidationStatus.WARN,
                metadata={"field": "last_verified_commit"},
            ),
        ),
    )

    payload = json.loads(report_to_json(report))

    assert payload["schema_version"] == 1
    assert payload["result"] == "WARN"
    assert payload["warnings"] == [
        {
            "code": "stale_policy",
            "message": "KB may be stale.",
            "path": "docs/kb/curated/payment.md",
            "severity": "WARN",
            "metadata": {"field": "last_verified_commit"},
        }
    ]


def test_report_schema_preserves_graph_cache_compatibility_metadata() -> None:
    report = ValidationResult(
        result=ValidationStatus.WARN,
        checked_at_commit="def456",
        metadata={
            "graph_cache": {
                "status": "loaded",
                "schema_version": 1,
                "format": "edges",
                "node_count": 2,
                "warnings": (),
            }
        },
    )

    payload = json.loads(report_to_json(report))

    assert payload["schema_version"] == 1
    assert payload["metadata"]["graph_cache"] == {
        "status": "loaded",
        "schema_version": 1,
        "format": "edges",
        "node_count": 2,
        "warnings": [],
    }
