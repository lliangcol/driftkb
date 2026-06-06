from __future__ import annotations

import json
import subprocess
from pathlib import Path

from driftkb.adapters.generic import GenericAdapter
from driftkb.adapters.java import JavaRegexAdapter
from driftkb.adapters.python import PythonAstAdapter
from driftkb.cli.main import main
from driftkb.fingerprints.snapshots import compare_fingerprint, load_snapshot, save_snapshot


def test_generic_fingerprint_hash_is_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "src" / "example.txt"
    source.parent.mkdir()
    source.write_text("hello\n", encoding="utf-8")

    adapter = GenericAdapter()
    first = adapter.extract(source, tmp_path)
    second = adapter.extract(source, tmp_path)

    assert first == second
    assert first.adapter == "generic"
    assert first.file == "src/example.txt"
    assert first.raw_hash == first.semantic_hash


def test_java_regex_adapter_extracts_fqcn_annotations_and_methods(tmp_path: Path) -> None:
    source = tmp_path / "src" / "main" / "java" / "com" / "example" / "PaymentService.java"
    source.parent.mkdir(parents=True)
    source.write_text(
        """
package com.example;

import org.springframework.stereotype.Service;

@Service
@Transactional
public class PaymentService {
    @XxlJob("paymentJob")
    public void runJob() {
    }

    protected String status() {
        return "ok";
    }
}
""".lstrip(),
        encoding="utf-8",
    )

    fingerprint = JavaRegexAdapter().extract(source, tmp_path)

    assert "com.example.PaymentService" in fingerprint.symbols
    assert "runJob" in fingerprint.symbols
    assert "status" in fingerprint.symbols
    assert "@Transactional" in fingerprint.annotations
    assert '@XxlJob("paymentJob")' in fingerprint.annotations
    assert fingerprint.metadata["package"] == "com.example"


def test_java_semantic_fingerprint_ignores_raw_whitespace_changes(tmp_path: Path) -> None:
    source = tmp_path / "src" / "main" / "java" / "com" / "example" / "PaymentService.java"
    source.parent.mkdir(parents=True)
    source.write_text(
        """
package com.example;

public class PaymentService {
    public void pay() {
    }
}
""".lstrip(),
        encoding="utf-8",
    )
    adapter = JavaRegexAdapter()
    original = adapter.extract(source, tmp_path)

    source.write_text(
        """
package com.example;

public class PaymentService {

    public void pay() {

    }
}
""".lstrip(),
        encoding="utf-8",
    )
    changed = adapter.extract(source, tmp_path)

    assert original.raw_hash != changed.raw_hash
    assert compare_fingerprint(changed, original)


def test_python_ast_adapter_extracts_symbols_imports_and_decorators(tmp_path: Path) -> None:
    source = tmp_path / "src" / "payments" / "service.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        """
from decimal import Decimal

@transactional
class PaymentService:
    @route("/pay")
    def pay(self, amount: Decimal) -> None:
        pass

def helper() -> None:
    pass
""".lstrip(),
        encoding="utf-8",
    )

    fingerprint = PythonAstAdapter().extract(source, tmp_path)

    assert fingerprint.adapter == "python"
    assert "src.payments.service.PaymentService" in fingerprint.symbols
    assert "src.payments.service.PaymentService.pay" in fingerprint.symbols
    assert "src.payments.service.helper" in fingerprint.symbols
    assert "@transactional" in fingerprint.annotations
    assert "@route" in fingerprint.annotations
    assert "decimal" in fingerprint.imports


def test_snapshot_compare_equal_and_changed(tmp_path: Path) -> None:
    source = tmp_path / "src" / "example.txt"
    source.parent.mkdir()
    source.write_text("hello\n", encoding="utf-8")
    adapter = GenericAdapter()
    original = adapter.extract(source, tmp_path)

    save_snapshot(tmp_path / ".driftkb" / "validation" / "fingerprints", original)
    loaded = load_snapshot(tmp_path / ".driftkb" / "validation" / "fingerprints", "src/example.txt", "generic")

    assert compare_fingerprint(original, loaded)

    source.write_text("changed\n", encoding="utf-8")
    changed = adapter.extract(source, tmp_path)

    assert not compare_fingerprint(changed, loaded)


def test_fingerprints_update_writes_stable_json(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo)
    _change_source(git_repo, "def pay():\n    return 2\n")

    assert main(["fingerprints", "update", "--repo-root", str(git_repo), "--all"]) == 0

    assert "updated 1 fingerprint snapshot(s)" in capsys.readouterr().out
    snapshot_paths = sorted((git_repo / ".driftkb" / "validation" / "fingerprints").rglob("*.json"))
    assert len(snapshot_paths) == 1
    data = json.loads(snapshot_paths[0].read_text(encoding="utf-8"))
    assert data["adapter"] == "generic"
    assert data["file"] == "src/payment/service.py"
    assert data["kb_path"] == "docs/kb/curated/payment.md"
    assert data["kb_last_verified_commit"]
    assert data["generated_at_commit"]
    assert data["source_changed_since_kb_last_verified"] is True
    assert list(data) == sorted(data)


def test_validate_does_not_trust_snapshot_generated_after_source_change(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo)
    _change_source(git_repo, "def pay():\n    return 2\n")

    assert main(["fingerprints", "update", "--repo-root", str(git_repo), "--all"]) == 0
    capsys.readouterr()

    assert main(["validate", "--repo-root", str(git_repo), "--no-write-report"]) == 0

    output = capsys.readouterr().out
    assert "DriftKB: WARN" in output
    assert "fingerprint snapshot matches current source but is not bound" in output
    assert "source changed since last_verified_commit" in output


def test_fingerprints_update_accept_current_advances_baseline(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo)
    _change_source(git_repo, "def pay():\n    return 2\n")
    head = _git(git_repo, "rev-parse", "HEAD").stdout.strip()

    assert main(["fingerprints", "update", "--repo-root", str(git_repo), "--all", "--accept-current"]) == 0

    output = capsys.readouterr().out
    assert "accepted current HEAD for 1 KB file(s)" in output
    kb_text = (git_repo / "docs" / "kb" / "curated" / "payment.md").read_text(encoding="utf-8")
    assert f"last_verified_commit: {head}" in kb_text
    data = json.loads(next((git_repo / ".driftkb" / "validation" / "fingerprints").rglob("*.json")).read_text())
    assert data["kb_last_verified_commit"] == head
    assert data["source_changed_since_kb_last_verified"] is False

    assert main(["validate", "--repo-root", str(git_repo), "--no-write-report"]) == 0
    assert "DriftKB: PASS" in capsys.readouterr().out


def test_validate_remains_conservative_without_snapshot(git_repo: Path, capsys) -> None:
    _baseline_repo(git_repo)
    _change_source(git_repo, "def pay():\n    return 2\n")

    assert main(["validate", "--repo-root", str(git_repo), "--no-write-report"]) == 0

    output = capsys.readouterr().out
    assert "DriftKB: WARN" in output
    assert "source changed since last_verified_commit" in output


def _baseline_repo(git_repo: Path) -> str:
    _init_git(git_repo)
    (git_repo / "src" / "payment").mkdir(parents=True)
    (git_repo / "src" / "payment" / "service.py").write_text("def pay():\n    return 1\n", encoding="utf-8")
    _commit_all(git_repo, "source baseline")
    base = _git(git_repo, "rev-parse", "HEAD").stdout.strip()
    _write_kb(git_repo, last_verified_commit=base)
    _commit_all(git_repo, "kb baseline")
    return base


def _change_source(git_repo: Path, content: str) -> None:
    (git_repo / "src" / "payment" / "service.py").write_text(content, encoding="utf-8")
    _commit_all(git_repo, "change payment source")


def _write_kb(git_repo: Path, *, last_verified_commit: str) -> None:
    kb_dir = git_repo / "docs" / "kb" / "curated"
    kb_dir.mkdir(parents=True, exist_ok=True)
    (kb_dir / "payment.md").write_text(
        f"""---
last_verified_commit: {last_verified_commit}
source_globs:
  - "src/payment/**/*.py"
stale_policy: warn
---
# Payment
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
