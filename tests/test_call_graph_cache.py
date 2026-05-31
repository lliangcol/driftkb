from __future__ import annotations

import json
from pathlib import Path

from driftkb.cli.main import main
from driftkb.graph.cache import load_graph_cache

from tests.test_validate import _commit_all, _git, _init_git


def test_missing_cache_loads_empty_with_warn_metadata(tmp_path: Path) -> None:
    cache = load_graph_cache(tmp_path / ".driftkb" / "call_graph_cache.json")

    assert cache.nodes == {}
    assert cache.get_callers("payment.PaymentService") == ()
    assert cache.metadata["status"] == "missing"
    assert cache.metadata["severity"] == "WARN"


def test_validate_propagates_callers_from_cache(git_repo: Path, capsys) -> None:
    base = _baseline_graph_repo(git_repo)
    _write_graph_cache(
        git_repo,
        {
            "payment.PaymentService": {
                "callers": ["api.PaymentController"],
                "callees": ["payment.PaymentRepository"],
            }
        },
    )
    _change_payment_source(git_repo)

    assert main(["validate", "--repo-root", str(git_repo), "--no-verify"]) == 0

    output = capsys.readouterr().out
    assert base not in output
    assert "DriftKB: WARN" in output
    assert "warnings: 2" in output
    report = json.loads((git_repo / ".driftkb" / "validation" / "last-run.json").read_text())
    assert [issue["code"] for issue in report["warnings"]] == ["source_changed", "graph_propagated"]
    propagated = report["warnings"][1]
    assert propagated["path"] == "docs/kb/curated/controller.md"
    assert propagated["severity"] == "WARN"
    assert propagated["metadata"]["related_anchor_symbol"] == "api.PaymentController"


def test_graph_propagation_deduplicates_duplicate_warnings(git_repo: Path, capsys) -> None:
    _baseline_graph_repo(git_repo, payment_anchors=("payment.PaymentService", "payment.PaymentFacade"))
    _write_graph_cache(
        git_repo,
        {
            "payment.PaymentService": {"callers": ["api.PaymentController"], "callees": []},
            "payment.PaymentFacade": {"callers": ["api.PaymentController"], "callees": []},
        },
    )
    _change_payment_source(git_repo)

    assert main(["validate", "--repo-root", str(git_repo), "--no-verify"]) == 0

    report = json.loads((git_repo / ".driftkb" / "validation" / "last-run.json").read_text())
    assert [issue["code"] for issue in report["warnings"]].count("graph_propagated") == 1
    assert "warnings: 2" in capsys.readouterr().out


def test_graph_anchors_outputs_curated_anchor_symbols(tmp_path: Path, capsys) -> None:
    kb_dir = tmp_path / "docs" / "kb" / "curated"
    kb_dir.mkdir(parents=True)
    _write_kb(
        kb_dir / "payment.md",
        last_verified_commit=None,
        source_globs=(),
        stale_policy="warn",
        anchor_symbols=("payment.PaymentService", "api.PaymentController"),
        propagate_callers=False,
    )
    _write_kb(
        kb_dir / "duplicate.md",
        last_verified_commit=None,
        source_globs=(),
        stale_policy="warn",
        anchor_symbols=("payment.PaymentService",),
        propagate_callers=False,
    )

    assert main(["graph", "anchors", "--repo-root", str(tmp_path)]) == 0

    assert json.loads(capsys.readouterr().out) == ["api.PaymentController", "payment.PaymentService"]


def _baseline_graph_repo(
    git_repo: Path,
    *,
    payment_anchors: tuple[str, ...] = ("payment.PaymentService",),
) -> str:
    _init_git(git_repo)
    (git_repo / "src" / "payment").mkdir(parents=True)
    (git_repo / "src" / "api").mkdir(parents=True)
    (git_repo / "src" / "payment" / "service.py").write_text("def pay():\n    return 1\n", encoding="utf-8")
    (git_repo / "src" / "api" / "controller.py").write_text("def controller():\n    return 1\n", encoding="utf-8")
    _commit_all(git_repo, "source baseline")
    base = _git(git_repo, "rev-parse", "HEAD").stdout.strip()

    kb_dir = git_repo / "docs" / "kb" / "curated"
    kb_dir.mkdir(parents=True, exist_ok=True)
    _write_kb(
        kb_dir / "payment.md",
        last_verified_commit=base,
        source_globs=("src/payment/**/*.py",),
        stale_policy="warn",
        anchor_symbols=payment_anchors,
        propagate_callers=True,
    )
    _write_kb(
        kb_dir / "controller.md",
        last_verified_commit=base,
        source_globs=("src/api/**/*.py",),
        stale_policy="warn",
        anchor_symbols=("api.PaymentController",),
        propagate_callers=False,
    )
    _commit_all(git_repo, "kb baseline")
    return base


def _write_graph_cache(git_repo: Path, nodes: dict[str, dict[str, list[str]]]) -> None:
    cache_path = git_repo / ".driftkb" / "call_graph_cache.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps({"schema_version": 1, "nodes": nodes}, indent=2), encoding="utf-8")
    _commit_all(git_repo, "graph cache")


def _change_payment_source(git_repo: Path) -> None:
    (git_repo / "src" / "payment" / "service.py").write_text("def pay():\n    return 2\n", encoding="utf-8")
    _commit_all(git_repo, "change payment source")


def _write_kb(
    path: Path,
    *,
    last_verified_commit: str | None,
    source_globs: tuple[str, ...],
    stale_policy: str,
    anchor_symbols: tuple[str, ...],
    propagate_callers: bool,
) -> None:
    last_verified_line = f"last_verified_commit: {last_verified_commit}\n" if last_verified_commit else ""
    source_block = ""
    if source_globs:
        source_lines = "\n".join(f'  - "{item}"' for item in source_globs)
        source_block = f"source_globs:\n{source_lines}\n"
    anchor_lines = "\n".join(f"  - {item}" for item in anchor_symbols)
    path.write_text(
        f"""---
{last_verified_line}{source_block}
stale_policy: {stale_policy}
anchor_symbols:
{anchor_lines}
propagate:
  callers: {str(propagate_callers).lower()}
  callees: false
---
# {path.stem}
""",
        encoding="utf-8",
    )
