from __future__ import annotations

from driftkb.core.models import ValidationResult, ValidationStatus

REPORT_SCHEMA_VERSION = 1


def empty_pass_report(checked_at_commit: str | None = None) -> ValidationResult:
    return ValidationResult(
        result=ValidationStatus.PASS,
        checked_at_commit=checked_at_commit,
    )
