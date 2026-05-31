from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from driftkb.core.models import ValidationStatus
from driftkb.verify.blocks import extract_verify_blocks, parse_expected, run_verify_block


def test_extract_verify_blocks_finds_multiple_markers() -> None:
    blocks = extract_verify_blocks(
        """# KB

```bash verify
rg "PaymentService" src
```

```python
print("not verify")
```

```verify
rg "OrderService" src
```
"""
    )

    assert len(blocks) == 2
    assert blocks[0].language == "bash verify"
    assert blocks[1].language == "verify"
    assert blocks[1].block_index == 1


def test_parse_expected_match_count() -> None:
    expected = parse_expected("# expected: match_count >= 2")

    assert expected is not None
    assert expected.minimum == 2


def test_run_rg_verify_passes_when_match_count_meets_expected(monkeypatch, tmp_path: Path) -> None:
    block = extract_verify_blocks(
        """```bash verify
rg -n "class PaymentService" src
# expected: match_count >= 1
```"""
    )[0]
    _mock_run(monkeypatch, returncode=0, stdout="src/payment.py:1:class PaymentService\n")

    result = run_verify_block(block, tmp_path)

    assert result.result == ValidationStatus.PASS
    assert result.actual_match_count == 1


def test_run_rg_verify_fails_when_match_count_is_too_low(monkeypatch, tmp_path: Path) -> None:
    block = extract_verify_blocks(
        """```bash verify
rg -n "class PaymentService" src
# expected: match_count >= 2
```"""
    )[0]
    _mock_run(monkeypatch, returncode=0, stdout="src/payment.py:1:class PaymentService\n")

    result = run_verify_block(block, tmp_path)

    assert result.result == ValidationStatus.FAIL
    assert result.actual_match_count == 1
    assert "expected match_count >= 2" in result.message


def test_run_rg_verify_counts_no_matches_from_exit_one(monkeypatch, tmp_path: Path) -> None:
    block = extract_verify_blocks(
        """```verify
rg "MissingService" src
# expected: match_count >= 1
```"""
    )[0]
    _mock_run(monkeypatch, returncode=1, stdout="")

    result = run_verify_block(block, tmp_path)

    assert result.result == ValidationStatus.FAIL
    assert result.actual_match_count == 0


def test_run_rg_verify_warns_on_rg_error(monkeypatch, tmp_path: Path) -> None:
    block = extract_verify_blocks(
        """```verify
rg "PaymentService" src
# expected: match_count >= 1
```"""
    )[0]
    _mock_run(monkeypatch, returncode=2, stdout="", stderr="regex parse error\n")

    result = run_verify_block(block, tmp_path)

    assert result.result == ValidationStatus.WARN
    assert result.actual_match_count is None
    assert "rg exited with code 2" in result.message
    assert result.stderr_sample == "<redacted 1 line(s)>"


def test_run_rg_verify_warns_when_rg_is_missing(monkeypatch, tmp_path: Path) -> None:
    block = extract_verify_blocks(
        """```verify
rg "PaymentService" src
# expected: match_count >= 1
```"""
    )[0]

    def missing_rg(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr("driftkb.verify.blocks.subprocess_run", missing_rg)

    result = run_verify_block(block, tmp_path)

    assert result.result == ValidationStatus.WARN
    assert "rg is not installed" in result.message


def test_run_rg_verify_warns_without_expected_assertion(tmp_path: Path) -> None:
    block = extract_verify_blocks(
        """```verify
rg "PaymentService" src
```"""
    )[0]

    result = run_verify_block(block, tmp_path)

    assert result.result == ValidationStatus.WARN
    assert "no expected assertion" in result.message


def test_run_rg_verify_rejects_unsafe_preprocessor(tmp_path: Path) -> None:
    block = extract_verify_blocks(
        """```verify
rg --pre "python steal.py" "PaymentService" src
# expected: match_count >= 1
```"""
    )[0]

    result = run_verify_block(block, tmp_path)

    assert result.result == ValidationStatus.WARN
    assert "unsafe option" in result.message


def test_run_rg_verify_rejects_paths_outside_source_root(tmp_path: Path) -> None:
    block = extract_verify_blocks(
        """```verify
rg "PaymentService" ../outside
# expected: match_count >= 1
```"""
    )[0]

    result = run_verify_block(block, tmp_path)

    assert result.result == ValidationStatus.WARN
    assert "relative to source root" in result.message


def test_run_rg_verify_rejects_option_paths_outside_source_root(tmp_path: Path) -> None:
    block = extract_verify_blocks(
        """```verify
rg --ignore-file ../ignore "PaymentService" src
# expected: match_count >= 1
```"""
    )[0]

    result = run_verify_block(block, tmp_path)

    assert result.result == ValidationStatus.WARN
    assert "option paths" in result.message


def test_run_rg_verify_rejects_files_mode_paths_outside_source_root(monkeypatch, tmp_path: Path) -> None:
    block = extract_verify_blocks(
        """```verify
rg --files ..
# expected: match_count >= 1
```"""
    )[0]

    def fail_if_called(*args, **kwargs):
        raise AssertionError("rg should not run when path validation fails")

    monkeypatch.setattr("driftkb.verify.blocks.subprocess_run", fail_if_called)

    result = run_verify_block(block, tmp_path)

    assert result.result == ValidationStatus.WARN
    assert "relative to source root" in result.message


def test_run_verify_warns_for_non_rg_when_shell_is_not_allowed(tmp_path: Path) -> None:
    block = extract_verify_blocks(
        """```bash verify
python scripts/check.py
# expected: match_count >= 1
```"""
    )[0]

    result = run_verify_block(block, tmp_path, allow_shell=False)

    assert result.result == ValidationStatus.WARN
    assert result.command == "python scripts/check.py"
    assert "only rg verify commands are supported" in result.message


def _mock_run(monkeypatch: pytest.MonkeyPatch, *, returncode: int, stdout: str, stderr: str = "") -> None:
    def fake_run(args, cwd, text, capture_output, timeout, check):
        return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout, stderr=stderr)

    monkeypatch.setattr("driftkb.verify.blocks.subprocess_run", fake_run)
