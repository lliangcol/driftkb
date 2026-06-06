from __future__ import annotations

import json
import subprocess
from pathlib import Path

from driftkb.cli.main import main


def test_validate_passes_when_sources_have_not_changed(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo, stale_policy="warn")

    exit_code = main(["validate", "--repo-root", str(git_repo)])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "DriftKB: PASS" in output
    assert "stale: 0" in output
    assert "warnings: 0" in output


def test_validate_warns_when_warn_policy_source_changes(git_repo: Path, capsys) -> None:
    base = _baseline_repo(git_repo, stale_policy="warn")
    _change_source(git_repo)

    exit_code = main(["validate", "--repo-root", str(git_repo)])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "DriftKB: WARN" in output
    assert "warnings: 1" in output
    assert "WARN docs/kb/curated/payment.md" in output
    assert "src/payment/service.py" in output

    report = json.loads((git_repo / ".driftkb" / "validation" / "last-run.json").read_text())
    assert report["result"] == "WARN"
    assert report["checked_at_commit"] != base
    assert report["warnings"][0]["code"] == "source_changed"
    assert report["warnings"][0]["metadata"]["matched_paths"] == ["src/payment/service.py"]


def test_validate_fails_when_fail_policy_source_changes(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo, stale_policy="fail")
    _change_source(git_repo)

    exit_code = main(["validate", "--repo-root", str(git_repo)])

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "DriftKB: FAIL" in output
    assert "stale: 1" in output
    assert "FAIL docs/kb/curated/payment.md" in output


def test_validate_checks_uncommitted_worktree_changes(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo, stale_policy="fail")
    (git_repo / "src" / "payment" / "service.py").write_text("def pay():\n    return 3\n", encoding="utf-8")

    exit_code = main(["validate", "--repo-root", str(git_repo), "--no-write-report", "--no-verify"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "DriftKB: FAIL" in output
    assert "src/payment/service.py" in output


def test_validate_checks_untracked_source_files(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo, stale_policy="fail", source_glob="src/payment/**/*.py")
    (git_repo / "src" / "payment" / "extra.py").write_text("def extra():\n    return 1\n", encoding="utf-8")

    exit_code = main(["validate", "--repo-root", str(git_repo), "--no-write-report", "--no-verify"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "src/payment/extra.py" in output


def test_validate_reviewed_paths_exempt_current_matched_dirty_paths(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo, stale_policy="fail")
    _add_reviewed_paths(
        git_repo,
        reviewed_paths=("src/payment/service.py",),
    )
    (git_repo / "src" / "payment" / "service.py").write_text("def pay():\n    return 2\n", encoding="utf-8")

    exit_code = main(["validate", "--repo-root", str(git_repo), "--no-write-report", "--no-verify"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "DriftKB: PASS" in output
    assert "source changed since last_verified_commit" not in output


def test_validate_reviewed_paths_only_exempt_listed_current_paths(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo, stale_policy="fail", source_glob="src/payment/**/*.py")
    _add_reviewed_paths(
        git_repo,
        reviewed_paths=("src/payment/service.py",),
    )
    (git_repo / "src" / "payment" / "service.py").write_text("def pay():\n    return 2\n", encoding="utf-8")
    (git_repo / "src" / "payment" / "extra.py").write_text("def extra():\n    return 1\n", encoding="utf-8")

    exit_code = main(["validate", "--repo-root", str(git_repo), "--no-write-report", "--no-verify"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "DriftKB: FAIL" in output
    assert "src/payment/extra.py" in output
    assert "src/payment/service.py" not in output


def test_validate_reviewed_paths_must_stay_in_source_globs(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo, stale_policy="fail")
    _add_reviewed_paths(
        git_repo,
        reviewed_paths=("docs/payment.md",),
    )
    (git_repo / "src" / "payment" / "service.py").write_text("def pay():\n    return 2\n", encoding="utf-8")

    exit_code = main(["validate", "--repo-root", str(git_repo), "--no-write-report", "--no-verify"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "reviewed_paths must be inside source_globs" in output


def test_validate_reviewed_paths_must_be_current_matched_dirty_paths(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo, stale_policy="fail", source_glob="src/payment/**/*.py")
    _add_reviewed_paths(
        git_repo,
        reviewed_paths=("src/payment/other.py",),
    )
    (git_repo / "src" / "payment" / "service.py").write_text("def pay():\n    return 2\n", encoding="utf-8")

    exit_code = main(["validate", "--repo-root", str(git_repo), "--no-write-report", "--no-verify"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "reviewed_paths can only cover current matched dirty paths" in output


def test_validate_reviewed_paths_fail_when_no_current_matched_dirty_paths(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo, stale_policy="fail")
    _add_reviewed_paths(
        git_repo,
        reviewed_paths=("src/payment/service.py",),
    )

    exit_code = main(["validate", "--repo-root", str(git_repo), "--no-write-report", "--no-verify"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "reviewed_paths can only cover current matched dirty paths" in output


def test_validate_skip_policy_ignores_source_changes(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo, stale_policy="skip")
    _change_source(git_repo)

    exit_code = main(["validate", "--repo-root", str(git_repo)])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "DriftKB: PASS" in output
    assert "warnings: 0" in output


def test_validate_strict_turns_warn_into_exit_code_one(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo, stale_policy="warn")
    _change_source(git_repo)

    exit_code = main(["validate", "--repo-root", str(git_repo), "--strict"])

    assert exit_code == 1
    assert "DriftKB: WARN" in capsys.readouterr().out


def test_validate_json_stdout_matches_written_report(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo, stale_policy="warn")
    _change_source(git_repo)

    assert main(["validate", "--repo-root", str(git_repo), "--format", "json"]) == 0

    stdout_report = json.loads(capsys.readouterr().out)
    written_report = json.loads((git_repo / ".driftkb" / "validation" / "last-run.json").read_text())
    assert stdout_report == written_report


def test_validate_no_write_report_skips_report_file(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo, stale_policy="warn")
    _change_source(git_repo)

    assert main(["validate", "--repo-root", str(git_repo), "--no-write-report"]) == 0

    assert not (git_repo / ".driftkb" / "validation" / "last-run.json").exists()
    assert "DriftKB: WARN" in capsys.readouterr().out


def test_validate_missing_last_verified_commit_warns(git_repo: Path, capsys) -> None:
    _init_git(git_repo)
    (git_repo / "src" / "payment").mkdir(parents=True)
    (git_repo / "src" / "payment" / "service.py").write_text("def pay():\n    return 1\n", encoding="utf-8")
    _write_kb(git_repo, last_verified_commit=None, stale_policy="warn")
    _commit_all(git_repo, "baseline")

    assert main(["validate", "--repo-root", str(git_repo), "--no-write-report"]) == 0

    output = capsys.readouterr().out
    assert "DriftKB: WARN" in output
    assert "last_verified_commit is missing" in output


def test_validate_treats_head_baseline_as_untrusted(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo, stale_policy="fail")
    kb_path = git_repo / "docs" / "kb" / "curated" / "payment.md"
    text = kb_path.read_text(encoding="utf-8")
    text = text.replace("last_verified_commit: ", "last_verified_commit: HEAD # old ")
    kb_path.write_text(text, encoding="utf-8")
    _commit_all(git_repo, "use moving baseline")

    exit_code = main(["validate", "--repo-root", str(git_repo), "--no-write-report", "--no-verify"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "last_verified_commit must be a fixed commit SHA" in output
    assert "source changed since last_verified_commit" in output


def test_validate_applies_source_filters_to_git_diff(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo, stale_policy="fail", source_glob="src/**/*.py")
    config = git_repo / ".driftkb" / "config.yml"
    config.parent.mkdir()
    config.write_text(
        """
version: 1
sources:
  root: .
  include:
    - "src/**/*"
  exclude:
    - "src/generated/**"
""".lstrip(),
        encoding="utf-8",
    )
    generated = git_repo / "src" / "generated" / "ignored.py"
    generated.parent.mkdir(parents=True)
    generated.write_text("def generated():\n    return 1\n", encoding="utf-8")
    _commit_all(git_repo, "change excluded generated source")

    exit_code = main(["validate", "--repo-root", str(git_repo), "--no-write-report", "--no-verify"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "DriftKB: PASS" in output
    assert "src/generated/ignored.py" not in output


def test_validate_invalid_frontmatter_fails(git_repo: Path, capsys) -> None:
    _init_git(git_repo)
    (git_repo / "src" / "payment").mkdir(parents=True)
    (git_repo / "src" / "payment" / "service.py").write_text("def pay():\n    return 1\n", encoding="utf-8")
    kb_dir = git_repo / "docs" / "kb" / "curated"
    kb_dir.mkdir(parents=True)
    (kb_dir / "payment.md").write_text(
        """---
source_globs:
  - 123
---
# Payment
""",
        encoding="utf-8",
    )
    _commit_all(git_repo, "baseline")

    exit_code = main(["validate", "--repo-root", str(git_repo), "--no-write-report", "--no-verify"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "DriftKB: FAIL" in output
    assert "source_globs must be a list of strings" in output


def test_validate_source_root_makes_globs_relative(git_repo: Path, capsys) -> None:
    base = _baseline_repo(git_repo, stale_policy="warn", source_glob="payment/**/*.py")
    _change_source(git_repo)

    assert main(["validate", "--repo-root", str(git_repo), "--source-root", "src"]) == 0

    output = capsys.readouterr().out
    assert base not in output
    assert "matched_paths:" in output
    assert "    - payment/service.py" in output


def test_validate_reports_stale_and_verify_failure(git_repo: Path, monkeypatch, capsys) -> None:
    _baseline_repo(
        git_repo,
        stale_policy="warn",
        body="""# Payment

```bash verify
rg -n "class PaymentService" src
# expected: match_count >= 1
```
""",
    )
    _change_source(git_repo)
    _mock_rg(monkeypatch, returncode=1, stdout="")

    exit_code = main(["validate", "--repo-root", str(git_repo)])

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "DriftKB: FAIL" in output
    assert "warnings: 1" in output
    assert "verify: 1" in output
    assert "FAIL docs/kb/curated/payment.md" in output
    report = json.loads((git_repo / ".driftkb" / "validation" / "last-run.json").read_text())
    assert report["warnings"][0]["code"] == "source_changed"
    assert report["verify"][0]["code"] == "verify_block_failed"
    assert report["verify"][0]["metadata"]["actual_match_count"] == 0


def test_validate_warns_for_verify_warning_without_failing(git_repo: Path, capsys) -> None:
    _baseline_repo(
        git_repo,
        stale_policy="warn",
        body="""# Payment

```bash verify
python scripts/check.py
# expected: match_count >= 1
```
""",
    )

    exit_code = main(["validate", "--repo-root", str(git_repo)])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "DriftKB: WARN" in output
    assert "verify: 1" in output
    assert "only rg verify commands are supported" in output


def test_validate_no_verify_skips_verify_blocks(git_repo: Path, capsys) -> None:
    _baseline_repo(
        git_repo,
        stale_policy="warn",
        body="""# Payment

```bash verify
python scripts/check.py
# expected: match_count >= 1
```
""",
    )

    exit_code = main(["validate", "--repo-root", str(git_repo), "--no-verify"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "DriftKB: PASS" in output
    assert "verify: 0" in output


def test_validate_errors_on_unknown_adapter(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo, stale_policy="warn")
    kb_path = git_repo / "docs" / "kb" / "curated" / "payment.md"
    kb_path.write_text(
        kb_path.read_text(encoding="utf-8").replace(
            "stale_policy: warn\n",
            "stale_policy: warn\nadapters:\n  - typo-adapter\n",
        ),
        encoding="utf-8",
    )
    _commit_all(git_repo, "configure typo adapter")

    exit_code = main(["validate", "--repo-root", str(git_repo), "--no-write-report", "--no-verify"])

    assert exit_code == 2
    assert "unknown adapter(s): typo-adapter" in capsys.readouterr().out


def test_validate_enterprise_java_profile_accepts_frontmatter_aliases(git_repo: Path, capsys) -> None:
    _init_git(git_repo)
    (git_repo / "src" / "payment").mkdir(parents=True)
    (git_repo / "src" / "payment" / "service.py").write_text("def pay():\n    return 1\n", encoding="utf-8")
    _commit_all(git_repo, "source baseline")
    base = _git(git_repo, "rev-parse", "HEAD").stdout.strip()
    kb_dir = git_repo / ".agents" / "kb" / "zh" / "curated"
    kb_dir.mkdir(parents=True)
    (kb_dir / "payment.md").write_text(
        f"""---
last_verified_commit: {base}
source_globs:
  - "src/payment/**/*.py"
stale_policy: warn_on_source_change
anchor_classes:
  - payment.PaymentService
---
# Payment
""",
        encoding="utf-8",
    )
    _commit_all(git_repo, "kb baseline")
    _change_source(git_repo)

    exit_code = main(["validate", "--repo-root", str(git_repo), "--profile", "enterprise-java", "--no-write-report"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "DriftKB: WARN" in output
    assert "WARN .agents/kb/zh/curated/payment.md" in output
    assert "src/payment/service.py" in output


def test_validate_default_profile_ignores_retrieval_policy_file(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo, stale_policy="warn")
    (git_repo / "RETRIEVAL_POLICY.json").write_text("[]\n", encoding="utf-8")
    _commit_all(git_repo, "add unrelated retrieval policy")

    exit_code = main(["validate", "--repo-root", str(git_repo), "--no-write-report", "--no-verify"])

    assert exit_code == 0
    assert "DriftKB: PASS" in capsys.readouterr().out


def test_validate_enterprise_java_profile_checks_retrieval_policy_defaults(git_repo: Path, capsys) -> None:
    _init_git(git_repo)
    (git_repo / "src").mkdir()
    (git_repo / "src" / "service.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    _commit_all(git_repo, "source baseline")
    base = _git(git_repo, "rev-parse", "HEAD").stdout.strip()
    kb_dir = git_repo / ".agents" / "kb" / "zh" / "curated"
    kb_dir.mkdir(parents=True)
    (kb_dir / "service.md").write_text(
        f"""---
last_verified_commit: {base}
source_globs: []
---
# Service
""",
        encoding="utf-8",
    )
    (git_repo / "RETRIEVAL_POLICY.json").write_text(
        json.dumps(
            {
                "default_include": [".agents/kb/zh/curated/**/*.md"],
                "default_exclude": [".agents/kb/zh/generated/**"],
            }
        ),
        encoding="utf-8",
    )
    _commit_all(git_repo, "add enterprise policy")

    exit_code = main(["validate", "--repo-root", str(git_repo), "--profile", "enterprise-java", "--no-write-report"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "DriftKB: FAIL" in output
    assert "default_exclude must exclude legacy/content" in output


def test_validate_enterprise_java_profile_checks_historical_content_disclaimer(git_repo: Path, capsys) -> None:
    _init_git(git_repo)
    (git_repo / "src").mkdir()
    (git_repo / "src" / "service.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    _commit_all(git_repo, "source baseline")
    base = _git(git_repo, "rev-parse", "HEAD").stdout.strip()
    kb_dir = git_repo / ".agents" / "kb" / "zh" / "curated" / "legacy" / "content"
    kb_dir.mkdir(parents=True)
    (kb_dir / "old.md").write_text(
        f"""---
last_verified_commit: {base}
source_globs: []
---
# Old
""",
        encoding="utf-8",
    )
    (git_repo / "RETRIEVAL_POLICY.json").write_text(
        json.dumps(
            {
                "default_include": [".agents/kb/zh/curated/**/*.md"],
                "default_exclude": [".agents/kb/zh/curated/legacy/content/**"],
            }
        ),
        encoding="utf-8",
    )
    _commit_all(git_repo, "add historical content")

    exit_code = main(["validate", "--repo-root", str(git_repo), "--profile", "enterprise-java", "--no-write-report"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "DriftKB: FAIL" in output
    assert "historical-only disclaimer" in output


def test_validate_enterprise_java_profile_accepts_valid_historical_content_policy(git_repo: Path, capsys) -> None:
    _init_git(git_repo)
    (git_repo / "src").mkdir()
    (git_repo / "src" / "service.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    _commit_all(git_repo, "source baseline")
    base = _git(git_repo, "rev-parse", "HEAD").stdout.strip()
    kb_dir = git_repo / ".agents" / "kb" / "zh" / "curated" / "legacy" / "content"
    kb_dir.mkdir(parents=True)
    (kb_dir / "old.md").write_text(
        f"""---
last_verified_commit: {base}
source_globs: []
---
# Old

仅作历史参考，不作为当前事实依据。
""",
        encoding="utf-8",
    )
    (git_repo / "RETRIEVAL_POLICY.json").write_text(
        json.dumps(
            {
                "default_include": [".agents/kb/zh/curated/**/*.md"],
                "default_exclude": ["legacy/content/**"],
            }
        ),
        encoding="utf-8",
    )
    _commit_all(git_repo, "add valid historical content")

    exit_code = main(["validate", "--repo-root", str(git_repo), "--profile", "enterprise-java", "--no-write-report"])

    assert exit_code == 0
    assert "DriftKB: PASS" in capsys.readouterr().out


def test_graph_anchors_enterprise_java_profile_reads_anchor_classes(git_repo: Path, capsys) -> None:
    _init_git(git_repo)
    kb_dir = git_repo / ".agents" / "kb" / "zh" / "curated"
    kb_dir.mkdir(parents=True)
    (kb_dir / "payment.md").write_text(
        """---
source_globs:
  - "src/payment/**/*.py"
stale_policy: fail_on_source_change
anchor_classes:
  - payment.PaymentService
---
# Payment
""",
        encoding="utf-8",
    )

    exit_code = main(["graph", "anchors", "--repo-root", str(git_repo), "--profile", "enterprise-java"])

    assert exit_code == 0
    assert "payment.PaymentService" in capsys.readouterr().out


def _baseline_repo(
    git_repo: Path,
    *,
    stale_policy: str,
    source_glob: str = "src/payment/**/*.py",
    body: str = "# Payment\n",
) -> str:
    _init_git(git_repo)
    (git_repo / "src" / "payment").mkdir(parents=True)
    (git_repo / "src" / "payment" / "service.py").write_text("def pay():\n    return 1\n", encoding="utf-8")
    _commit_all(git_repo, "source baseline")
    base = _git(git_repo, "rev-parse", "HEAD").stdout.strip()
    _write_kb(git_repo, last_verified_commit=base, stale_policy=stale_policy, source_glob=source_glob, body=body)
    _commit_all(git_repo, "kb baseline")
    return base


def _change_source(git_repo: Path) -> None:
    (git_repo / "src" / "payment" / "service.py").write_text("def pay():\n    return 2\n", encoding="utf-8")
    _commit_all(git_repo, "change payment source")


def _add_reviewed_paths(git_repo: Path, *, reviewed_paths: tuple[str, ...]) -> None:
    kb_path = git_repo / "docs" / "kb" / "curated" / "payment.md"
    reviewed_block = "\n".join(f'  - "{path}"' for path in reviewed_paths)
    kb_path.write_text(
        kb_path.read_text(encoding="utf-8").replace(
            "stale_policy: fail\n",
            f"""stale_policy: fail
reviewed_change_scope: matched_dirty_paths
reviewed_at: 2026-05-31
reviewed_paths:
{reviewed_block}
""",
        ),
        encoding="utf-8",
    )


def _write_kb(
    git_repo: Path,
    *,
    last_verified_commit: str | None,
    stale_policy: str,
    source_glob: str = "src/payment/**/*.py",
    body: str = "# Payment\n",
) -> None:
    kb_dir = git_repo / "docs" / "kb" / "curated"
    kb_dir.mkdir(parents=True, exist_ok=True)
    last_verified_line = f"last_verified_commit: {last_verified_commit}\n" if last_verified_commit else ""
    (kb_dir / "payment.md").write_text(
        f"""---
{last_verified_line}source_globs:
  - "{source_glob}"
stale_policy: {stale_policy}
---
{body}
""",
        encoding="utf-8",
    )


def _init_git(path: Path) -> None:
    _git(path, "init")
    _git(path, "config", "user.name", "DriftKB Tests")
    _git(path, "config", "user.email", "tests@example.invalid")


def _commit_all(path: Path, message: str) -> None:
    _git(path, "add", ".")
    _git(path, "commit", "-m", message)


def _git(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=path,
        text=True,
        capture_output=True,
        check=True,
    )


def _mock_rg(monkeypatch, *, returncode: int, stdout: str, stderr: str = "") -> None:
    def fake_run(args, cwd, text, capture_output, timeout, check):
        return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout, stderr=stderr)

    monkeypatch.setattr("driftkb.verify.blocks.subprocess_run", fake_run)
