from __future__ import annotations

import subprocess
from pathlib import Path
import json

from driftkb.cli.main import main
from driftkb.core.frontmatter import parse_markdown_frontmatter


def test_promote_generated_stub_success(git_repo: Path, capsys) -> None:
    head = _baseline_repo(git_repo)

    assert main(["promote", "docs/kb/generated/payment-service-stub.md", "--repo-root", str(git_repo)]) == 0

    output = capsys.readouterr().out
    source = git_repo / "docs" / "kb" / "generated" / "payment-service-stub.md"
    target = git_repo / "docs" / "kb" / "curated" / "payment-service-stub.md"
    assert "DriftKB promote: PASS" in output
    assert "mode: write" in output
    assert not source.exists()
    assert target.is_file()
    assert "# [Needs review] com.example.PaymentService" in target.read_text(encoding="utf-8")

    frontmatter, _ = parse_markdown_frontmatter(target)
    assert frontmatter["kind"] == "curated"
    assert frontmatter["last_verified_commit"] == head
    assert frontmatter["stale_policy"] == "fail"
    assert "generated_from_commit" not in frontmatter
    assert "generator" not in frontmatter
    assert "validation_status" not in frontmatter
    assert "reviewed_by" not in frontmatter
    assert frontmatter["source_globs"] == ["src/main/java/com/example/PaymentService.java"]
    assert frontmatter["anchor_symbols"] == ["com.example.PaymentService"]
    assert frontmatter["owner"] == "payments"
    assert frontmatter["tags"] == ["payments", "generated"]


def test_promote_rejects_non_generated_file(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo)
    generated = git_repo / "docs" / "kb" / "generated" / "payment-service-stub.md"
    text = generated.read_text(encoding="utf-8").replace("kind: generated", "kind: curated")
    generated.write_text(text, encoding="utf-8")

    assert main(["promote", str(generated), "--repo-root", str(git_repo)]) == 2

    assert "only KB files with kind: generated" in capsys.readouterr().out
    assert generated.exists()


def test_promote_rejects_existing_target(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo)
    target = git_repo / "docs" / "kb" / "curated" / "payment-service-stub.md"
    target.parent.mkdir(parents=True)
    target.write_text("---\nkind: curated\nsource_globs:\n  - \"src/**/*.py\"\n---\n# Existing\n", encoding="utf-8")

    assert main(["promote", "docs/kb/generated/payment-service-stub.md", "--repo-root", str(git_repo)]) == 2

    assert "target curated KB already exists" in capsys.readouterr().out


def test_promote_dry_run_does_not_modify_files(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo)
    source = git_repo / "docs" / "kb" / "generated" / "payment-service-stub.md"
    before = source.read_text(encoding="utf-8")

    assert main(["promote", str(source), "--repo-root", str(git_repo), "--dry-run", "--stale-policy", "warn"]) == 0

    output = capsys.readouterr().out
    assert "mode: dry-run" in output
    assert "stale_policy: warn" in output
    assert source.read_text(encoding="utf-8") == before
    assert not (git_repo / "docs" / "kb" / "curated" / "payment-service-stub.md").exists()


def test_promote_rejects_pending_human_review(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo, validation_status="pending_human_review", reviewed_by="reviewer@example.invalid")

    assert main(["promote", "docs/kb/generated/payment-service-stub.md", "--repo-root", str(git_repo)]) == 2

    output = capsys.readouterr().out
    assert "validation_status must be human_reviewed" in output
    assert (git_repo / "docs" / "kb" / "generated" / "payment-service-stub.md").exists()


def test_promote_rejects_missing_reviewer(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo, reviewed_by=None)

    assert main(["promote", "docs/kb/generated/payment-service-stub.md", "--repo-root", str(git_repo)]) == 2

    assert "reviewed_by must identify" in capsys.readouterr().out


def test_promote_enterprise_profile_accepts_review_status_and_reviewer_aliases(git_repo: Path, capsys) -> None:
    _write_enterprise_project(git_repo)
    _git(git_repo, "init")
    _git(git_repo, "config", "user.name", "DriftKB Tests")
    _git(git_repo, "config", "user.email", "tests@example.invalid")
    _git(git_repo, "add", ".")
    _git(git_repo, "commit", "-m", "baseline")
    head = _git(git_repo, "rev-parse", "HEAD").stdout.strip()

    assert (
        main(
            [
                "promote",
                ".agents/kb/zh/generated/payment-service-stub.md",
                "--repo-root",
                str(git_repo),
                "--profile",
                "enterprise-java",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    target = git_repo / ".agents" / "kb" / "zh" / "curated" / "payment-service-stub.md"
    frontmatter, _ = parse_markdown_frontmatter(target)
    assert "DriftKB promote: PASS" in output
    assert frontmatter["kind"] == "curated"
    assert frontmatter["last_verified_commit"] == head
    assert frontmatter["anchor_symbols"] == ["com.example.PaymentService"]
    assert "anchor_classes" not in frontmatter
    assert "review_status" not in frontmatter
    assert "reviewer" not in frontmatter

    assert main(["validate", "--repo-root", str(git_repo), "--profile", "enterprise-java", "--no-write-report", "--no-verify"]) == 0


def test_promote_frontmatter_fields_are_updated_after_human_review(git_repo: Path, capsys) -> None:
    head = _baseline_repo(git_repo)

    assert main(["promote", "docs/kb/generated/payment-service-stub.md", "--repo-root", str(git_repo), "--stale-policy", "warn"]) == 0

    capsys.readouterr()
    frontmatter, _ = parse_markdown_frontmatter(git_repo / "docs" / "kb" / "curated" / "payment-service-stub.md")
    assert frontmatter["kind"] == "curated"
    assert frontmatter["last_verified_commit"] == head
    assert frontmatter["stale_policy"] == "warn"
    assert "generated_from_commit" not in frontmatter
    assert "generator" not in frontmatter
    assert "validation_status" not in frontmatter
    assert "reviewed_by" not in frontmatter


def test_promote_rejects_staged_changes(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo)
    (git_repo / "staged.txt").write_text("staged\n", encoding="utf-8")
    _git(git_repo, "add", "staged.txt")

    assert main(["promote", "docs/kb/generated/payment-service-stub.md", "--repo-root", str(git_repo)]) == 2

    assert "staged changes" in capsys.readouterr().out
    assert (git_repo / "docs" / "kb" / "generated" / "payment-service-stub.md").exists()


def test_promote_then_validate_reads_curated_file(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo)

    assert main(["promote", "docs/kb/generated/payment-service-stub.md", "--repo-root", str(git_repo)]) == 0
    capsys.readouterr()

    assert main(["validate", "--repo-root", str(git_repo), "--no-write-report"]) == 0

    output = capsys.readouterr().out
    assert "DriftKB: PASS" in output
    assert "stale: 0" in output


def test_promote_can_update_fingerprint_snapshot(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo)

    assert main(
        [
            "promote",
            "docs/kb/generated/payment-service-stub.md",
            "--repo-root",
            str(git_repo),
            "--update-fingerprints",
        ]
    ) == 0

    output = capsys.readouterr().out
    assert "fingerprints_updated: 1" in output
    snapshots = sorted((git_repo / ".driftkb" / "validation" / "fingerprints").rglob("*.json"))
    assert len(snapshots) == 1
    data = json.loads(snapshots[0].read_text(encoding="utf-8"))
    assert data["adapter"] == "generic"
    assert data["file"] == "src/main/java/com/example/PaymentService.java"


def test_promote_update_fingerprints_rejects_dirty_covered_source(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo)
    source = git_repo / "src" / "main" / "java" / "com" / "example" / "PaymentService.java"
    source.write_text(
        """
package com.example;

public class PaymentService {
    public void changed() {
    }
}
""".lstrip(),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "promote",
                "docs/kb/generated/payment-service-stub.md",
                "--repo-root",
                str(git_repo),
                "--update-fingerprints",
            ]
        )
        == 2
    )

    output = capsys.readouterr().out
    assert "covered source files have uncommitted changes" in output
    assert "src/main/java/com/example/PaymentService.java" in output
    assert (git_repo / "docs" / "kb" / "generated" / "payment-service-stub.md").exists()
    assert not (git_repo / "docs" / "kb" / "curated" / "payment-service-stub.md").exists()
    assert not list((git_repo / ".driftkb" / "validation" / "fingerprints").glob("**/*.json"))


def test_promote_uses_custom_config_path(git_repo: Path, capsys) -> None:
    head = _custom_config_repo(git_repo)

    assert (
        main(
            [
                "promote",
                "knowledge/generated/service-stub.md",
                "--repo-root",
                str(git_repo),
                "--config",
                ".driftkb/custom.yml",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    source = git_repo / "knowledge" / "generated" / "service-stub.md"
    target = git_repo / "knowledge" / "curated" / "service-stub.md"
    assert "DriftKB promote: PASS" in output
    assert f"last_verified_commit: {head}" in output
    assert not source.exists()
    assert target.is_file()


def test_promote_rejects_unknown_adapter_before_moving(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo)
    generated = git_repo / "docs" / "kb" / "generated" / "payment-service-stub.md"
    generated.write_text(
        generated.read_text(encoding="utf-8").replace(
            "anchor_symbols:\n  - com.example.PaymentService\n",
            "anchor_symbols:\n  - com.example.PaymentService\nadapters:\n  - java-typo\n",
        ),
        encoding="utf-8",
    )

    assert main(["promote", "docs/kb/generated/payment-service-stub.md", "--repo-root", str(git_repo)]) == 2

    assert "unknown adapter(s): java-typo" in capsys.readouterr().out
    assert generated.exists()
    assert not (git_repo / "docs" / "kb" / "curated" / "payment-service-stub.md").exists()


def _baseline_repo(
    git_repo: Path,
    *,
    validation_status: str = "human_reviewed",
    reviewed_by: str | None = "reviewer@example.invalid",
) -> str:
    _write_project(git_repo, validation_status=validation_status, reviewed_by=reviewed_by)
    _git(git_repo, "init")
    _git(git_repo, "config", "user.name", "DriftKB Tests")
    _git(git_repo, "config", "user.email", "tests@example.invalid")
    _git(git_repo, "add", ".")
    _git(git_repo, "commit", "-m", "baseline")
    return _git(git_repo, "rev-parse", "HEAD").stdout.strip()


def _custom_config_repo(path: Path) -> str:
    config_dir = path / ".driftkb"
    config_dir.mkdir()
    (config_dir / "custom.yml").write_text(
        """
version: 1
kb:
  curated_dir: knowledge/curated
  generated_dir: knowledge/generated
""".lstrip(),
        encoding="utf-8",
    )
    source = path / "src" / "service.py"
    source.parent.mkdir()
    source.write_text("def pay():\n    return 1\n", encoding="utf-8")
    generated = path / "knowledge" / "generated" / "service-stub.md"
    generated.parent.mkdir(parents=True)
    generated.write_text(
        """---
kind: generated
topic: service-stub
risk: high
generated_from_commit: unknown
generator: driftkb gaps detect
validation_status: human_reviewed
reviewed_by: reviewer@example.invalid
source_globs:
  - "src/service.py"
anchor_symbols:
  - pay
---
# Service

Human-authored review content.
""",
        encoding="utf-8",
    )
    _git(path, "init")
    _git(path, "config", "user.name", "DriftKB Tests")
    _git(path, "config", "user.email", "tests@example.invalid")
    _git(path, "add", ".")
    _git(path, "commit", "-m", "baseline")
    return _git(path, "rev-parse", "HEAD").stdout.strip()


def _write_project(path: Path, *, validation_status: str, reviewed_by: str | None) -> None:
    source = path / "src" / "main" / "java" / "com" / "example" / "PaymentService.java"
    source.parent.mkdir(parents=True)
    source.write_text(
        """
package com.example;

public class PaymentService {
}
""".lstrip(),
        encoding="utf-8",
    )
    generated = path / "docs" / "kb" / "generated" / "payment-service-stub.md"
    generated.parent.mkdir(parents=True)
    reviewed_by_line = f"reviewed_by: {reviewed_by}\n" if reviewed_by is not None else ""
    generated.write_text(
        f"""---
kind: generated
topic: payment-service-stub
risk: high
generated_from_commit: unknown
generator: driftkb gaps detect
validation_status: {validation_status}
{reviewed_by_line}reviewed_at: 2026-05-31
source_globs:
  - "src/main/java/com/example/PaymentService.java"
anchor_symbols:
  - com.example.PaymentService
owner: payments
tags:
  - payments
  - generated
---
# [Needs review] com.example.PaymentService

Human-authored review content.
""",
        encoding="utf-8",
    )


def _write_enterprise_project(path: Path) -> None:
    source = path / "src" / "main" / "java" / "com" / "example" / "PaymentService.java"
    source.parent.mkdir(parents=True)
    source.write_text(
        """
package com.example;

public class PaymentService {
}
""".lstrip(),
        encoding="utf-8",
    )
    generated = path / ".agents" / "kb" / "zh" / "generated" / "payment-service-stub.md"
    generated.parent.mkdir(parents=True)
    generated.write_text(
        """---
kind: generated
topic: payment-service-stub
risk: high
generated_from_commit: unknown
generator: driftkb gaps detect
review_status: reviewed
reviewer: reviewer@example.invalid
source_globs:
  - "src/main/java/com/example/PaymentService.java"
anchor_classes:
  - com.example.PaymentService
---
# [Needs review] com.example.PaymentService

Human-authored review content.
""",
        encoding="utf-8",
    )


def _git(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=path,
        text=True,
        capture_output=True,
        check=True,
    )
