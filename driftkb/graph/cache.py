from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GraphNode:
    callers: tuple[str, ...] = ()
    callees: tuple[str, ...] = ()


@dataclass(frozen=True)
class CallGraphCache:
    path: Path
    nodes: dict[str, GraphNode]
    metadata: dict[str, Any]

    def get_callers(self, symbol: str) -> tuple[str, ...]:
        node = self.nodes.get(symbol)
        return node.callers if node is not None else ()

    def get_callees(self, symbol: str) -> tuple[str, ...]:
        node = self.nodes.get(symbol)
        return node.callees if node is not None else ()


def load_graph_cache(path: Path) -> CallGraphCache:
    if not path.exists():
        return _empty_cache(
            path,
            status="missing",
            warnings=("call graph cache file is missing; graph propagation is disabled",),
        )

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _empty_cache(path, status="invalid", warnings=(f"call graph cache could not be read: {exc}",))

    warnings = _schema_warnings(raw)
    if warnings:
        return _empty_cache(path, status="invalid", warnings=tuple(warnings))

    nodes: dict[str, GraphNode] = {}
    for symbol, raw_node in raw["nodes"].items():
        nodes[symbol] = GraphNode(
            callers=tuple(raw_node.get("callers", [])),
            callees=tuple(raw_node.get("callees", [])),
        )

    return CallGraphCache(
        path=path,
        nodes=nodes,
        metadata={
            "path": path.as_posix(),
            "status": "loaded",
            "schema_version": raw["schema_version"],
            "node_count": len(nodes),
            "warnings": (),
        },
    )


def load_call_graph_cache(path: Path) -> CallGraphCache | None:
    cache = load_graph_cache(path)
    return None if cache.metadata["status"] == "missing" else cache


def _schema_warnings(raw: Any) -> list[str]:
    warnings: list[str] = []
    if not isinstance(raw, dict):
        return ["call graph cache root must be a JSON object"]
    if raw.get("schema_version") != 1:
        warnings.append("call graph cache schema_version must be 1")
    nodes = raw.get("nodes")
    if not isinstance(nodes, dict):
        warnings.append("call graph cache nodes must be an object")
        return warnings
    for symbol, node in nodes.items():
        if not isinstance(symbol, str):
            warnings.append("call graph cache node keys must be strings")
            continue
        if not isinstance(node, dict):
            warnings.append(f"call graph cache node `{symbol}` must be an object")
            continue
        for edge_key in ("callers", "callees"):
            edges = node.get(edge_key, [])
            if not isinstance(edges, list) or not all(isinstance(item, str) for item in edges):
                warnings.append(f"call graph cache node `{symbol}` field `{edge_key}` must be a list of strings")
    return warnings


def _empty_cache(path: Path, *, status: str, warnings: tuple[str, ...]) -> CallGraphCache:
    return CallGraphCache(
        path=path,
        nodes={},
        metadata={
            "path": path.as_posix(),
            "status": status,
            "schema_version": None,
            "node_count": 0,
            "warnings": warnings,
            "severity": "WARN",
        },
    )
