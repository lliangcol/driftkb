from __future__ import annotations

import subprocess
from pathlib import Path

from driftkb.cli.main import main


def test_gaps_detect_finds_gap_without_curated_anchor(git_repo: Path, capsys) -> None:
    _write_project(git_repo)
    _init_and_commit(git_repo)

    assert main(["gaps", "detect", "--repo-root", str(git_repo)]) == 0

    output = capsys.readouterr().out
    assert "DriftKB gaps: WARN" in output
    assert "gaps: 1" in output
    assert "com.example.PaymentService" in output


def test_gaps_detect_respects_whitelist(git_repo: Path, capsys) -> None:
    _write_project(git_repo)
    whitelist = git_repo / ".driftkb" / "gap_whitelist.txt"
    whitelist.write_text("# reviewed elsewhere\ncom.example.*\n", encoding="utf-8")
    _init_and_commit(git_repo)

    assert main(["gaps", "detect", "--repo-root", str(git_repo)]) == 0

    output = capsys.readouterr().out
    assert "DriftKB gaps: PASS" in output
    assert "gaps: 0" in output
    assert "skipped_whitelisted: 1" in output


def test_gaps_detect_dry_run_does_not_write_stub(git_repo: Path, capsys) -> None:
    _write_project(git_repo)
    _init_and_commit(git_repo)

    assert main(["gaps", "detect", "--repo-root", str(git_repo), "--dry-run"]) == 0

    capsys.readouterr()
    assert not (git_repo / "docs" / "kb" / "generated" / "payment-service-stub.md").exists()


def test_gaps_detect_write_creates_generated_stub(git_repo: Path, capsys) -> None:
    _write_project(git_repo)
    head = _init_and_commit(git_repo)

    assert main(["gaps", "detect", "--repo-root", str(git_repo), "--write"]) == 0

    output = capsys.readouterr().out
    stub = git_repo / "docs" / "kb" / "generated" / "payment-service-stub.md"
    assert "written: 1" in output
    assert stub.is_file()
    assert not (git_repo / "docs" / "kb" / "curated" / "payment.md").exists()

    text = stub.read_text(encoding="utf-8")
    assert "kind: generated" in text
    assert "topic: payment-service-stub" in text
    assert "risk: high" in text
    assert f"generated_from_commit: {head}" in text
    assert "generator: driftkb gaps detect" in text
    assert "validation_status: pending_human_review" in text
    assert '  - "src/main/java/com/example/PaymentService.java"' in text
    assert "  - com.example.PaymentService" in text
    assert "<!-- Auto-generated stub. Human review required before promotion. -->" in text
    assert "- adapter: java" in text
    assert "  - Transactional" in text


def test_gaps_detect_enterprise_profile_writes_compatible_stub(git_repo: Path, capsys) -> None:
    _write_project(git_repo, adapter="enterprise-java")
    head = _init_and_commit(git_repo)

    assert main(["gaps", "detect", "--repo-root", str(git_repo), "--profile", "enterprise-java", "--write"]) == 0

    output = capsys.readouterr().out
    stub = git_repo / ".agents" / "kb" / "zh" / "generated" / "payment-service-stub.md"
    assert "written: 1" in output
    text = stub.read_text(encoding="utf-8")
    assert f"generated_from_commit: {head}" in text
    assert "review_status: pending_review" in text
    assert "anchor_classes:" in text
    assert "anchor_symbols:" not in text


def test_gaps_detect_enterprise_profile_uses_kb_section_map_as_existing_coverage(git_repo: Path, capsys) -> None:
    _write_project(git_repo, adapter="enterprise-java")
    section_map = git_repo / ".agents" / "kb" / "zh" / "_validation" / "kb_section_map.json"
    section_map.parent.mkdir(parents=True)
    section_map.write_text(
        """
{
  "schema_version": 1,
  "sections": [
    {
      "path": ".agents/kb/zh/curated/payment.md",
      "anchor_classes": ["com.example.PaymentService"]
    }
  ]
}
""".lstrip(),
        encoding="utf-8",
    )
    _init_and_commit(git_repo)

    assert main(["gaps", "detect", "--repo-root", str(git_repo), "--profile", "enterprise-java"]) == 0

    output = capsys.readouterr().out
    assert "DriftKB gaps: PASS" in output
    assert "gaps: 0" in output


def test_gaps_detect_write_avoids_filename_collisions(git_repo: Path, capsys) -> None:
    _write_project(git_repo)
    second = git_repo / "src" / "main" / "java" / "com" / "other" / "PaymentService.java"
    second.parent.mkdir(parents=True)
    second.write_text(
        """
package com.other;

@Transactional
public class PaymentService {
}
""".lstrip(),
        encoding="utf-8",
    )
    _init_and_commit(git_repo)

    assert main(["gaps", "detect", "--repo-root", str(git_repo), "--write", "--risk", "all"]) == 0

    output = capsys.readouterr().out
    stubs = sorted((git_repo / "docs" / "kb" / "generated").glob("payment-service-stub*.md"))
    assert "written: 2" in output
    assert len(stubs) == 2
    assert stubs[0].name != stubs[1].name
    assert {stub.read_text(encoding="utf-8").split("anchor_symbols:\n  - ", 1)[1].splitlines()[0] for stub in stubs} == {
        "com.example.PaymentService",
        "com.other.PaymentService",
    }


def test_gaps_detect_errors_on_unknown_adapter(git_repo: Path, capsys) -> None:
    _write_project(git_repo)
    config = git_repo / ".driftkb" / "config.yml"
    config.write_text(config.read_text(encoding="utf-8").replace("    - java\n", "    - java-typo\n"), encoding="utf-8")
    _init_and_commit(git_repo)

    assert main(["gaps", "detect", "--repo-root", str(git_repo)]) == 2

    assert "unknown adapter(s): java-typo" in capsys.readouterr().out


def _write_project(path: Path, *, adapter: str = "java") -> None:
    config_dir = path / ".driftkb"
    config_dir.mkdir()
    (config_dir / "config.yml").write_text(
        f"""
version: 1
adapters:
  enabled:
    - {adapter}
gaps:
  enabled: true
  whitelist_path: .driftkb/gap_whitelist.txt
  risk_patterns:
    - "@Transactional"
    - "@RocketMQMessageListener"
    - "@XxlJob"
    - "@DS"
""".lstrip(),
        encoding="utf-8",
    )
    source = path / "src" / "main" / "java" / "com" / "example" / "PaymentService.java"
    source.parent.mkdir(parents=True)
    source.write_text(
        """
package com.example;

@Transactional
public class PaymentService {
    public void pay() {
    }
}
""".lstrip(),
        encoding="utf-8",
    )


def _init_and_commit(path: Path) -> str:
    _git(path, "init")
    _git(path, "config", "user.name", "DriftKB Tests")
    _git(path, "config", "user.email", "tests@example.invalid")
    _git(path, "add", ".")
    _git(path, "commit", "-m", "baseline")
    return _git(path, "rev-parse", "HEAD").stdout.strip()


def _git(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=path,
        text=True,
        capture_output=True,
        check=True,
    )
