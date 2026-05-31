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

    normalized, warnings = _normalize_cache(raw)
    if warnings:
        return _empty_cache(path, status="invalid", warnings=tuple(warnings))

    nodes: dict[str, GraphNode] = {}
    for symbol, raw_node in normalized["nodes"].items():
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
            "schema_version": normalized["schema_version"],
            "node_count": len(nodes),
            "format": normalized["format"],
            "warnings": (),
        },
    )


def load_call_graph_cache(path: Path) -> CallGraphCache | None:
    cache = load_graph_cache(path)
    return None if cache.metadata["status"] == "missing" else cache


def _normalize_cache(raw: Any) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    if not isinstance(raw, dict):
        return {}, ["call graph cache root must be a JSON object"]
    if raw.get("schema_version") != 1:
        warnings.append("call graph cache schema_version must be 1")
        return {}, warnings

    if isinstance(raw.get("nodes"), list):
        raw = {**raw, "nodes": _nodes_list_to_mapping(raw["nodes"])}
        if raw["nodes"] is None:
            return {}, ["call graph cache nodes list entries must be objects with a string symbol"]
        normalized_format = "nodes_list"
    elif "edges" in raw and "nodes" not in raw:
        edge_nodes, edge_warnings = _edges_to_nodes(raw.get("edges"))
        if edge_warnings:
            return {}, edge_warnings
        raw = {**raw, "nodes": edge_nodes}
        normalized_format = "edges"
    else:
        normalized_format = "nodes"

    nodes = raw.get("nodes")
    if not isinstance(nodes, dict):
        warnings.append("call graph cache nodes must be an object")
        return {}, warnings
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
    return {
        "schema_version": raw["schema_version"],
        "nodes": nodes,
        "format": normalized_format,
    }, warnings


def _nodes_list_to_mapping(nodes: list[Any]) -> dict[str, Any] | None:
    mapped: dict[str, Any] = {}
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("symbol"), str):
            return None
        mapped[node["symbol"]] = {
            "callers": node.get("callers", []),
            "callees": node.get("callees", []),
        }
    return mapped


def _edges_to_nodes(edges: Any) -> tuple[dict[str, dict[str, list[str]]], list[str]]:
    if not isinstance(edges, list):
        return {}, ["call graph cache edges must be a list"]

    nodes: dict[str, dict[str, list[str]]] = {}
    for edge in edges:
        if not isinstance(edge, dict):
            return {}, ["call graph cache edge entries must be objects"]
        caller = edge.get("caller", edge.get("from"))
        callee = edge.get("callee", edge.get("to"))
        if not isinstance(caller, str) or not isinstance(callee, str):
            return {}, ["call graph cache edge entries must include string caller/callee or from/to"]
        nodes.setdefault(caller, {"callers": [], "callees": []})
        nodes.setdefault(callee, {"callers": [], "callees": []})
        if callee not in nodes[caller]["callees"]:
            nodes[caller]["callees"].append(callee)
        if caller not in nodes[callee]["callers"]:
            nodes[callee]["callers"].append(caller)
    return nodes, []


def _empty_cache(path: Path, *, status: str, warnings: tuple[str, ...]) -> CallGraphCache:
    return CallGraphCache(
        path=path,
        nodes={},
        metadata={
            "path": path.as_posix(),
            "status": status,
            "schema_version": None,
            "node_count": 0,
            "format": None,
            "warnings": warnings,
            "severity": "WARN",
        },
    )
