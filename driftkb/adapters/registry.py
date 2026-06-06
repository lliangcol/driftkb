from __future__ import annotations

from importlib.metadata import EntryPoint, entry_points

from driftkb.adapters.base import FingerprintAdapter
from driftkb.adapters.generic import GenericAdapter

ADAPTER_ENTRY_POINT_GROUP = "driftkb.adapters"


def build_adapters(names: tuple[str, ...]) -> tuple[FingerprintAdapter, ...]:
    adapters: list[FingerprintAdapter] = []
    unknown: list[str] = []
    for name in names:
        normalized = name.lower()
        if normalized == "generic":
            adapters.append(GenericAdapter())
        elif normalized in {"java", "java-regex"}:
            from driftkb.adapters.java import JavaRegexAdapter

            adapters.append(JavaRegexAdapter())
        elif normalized in {"enterprise-java", "enterprise_java"}:
            from driftkb.adapters.enterprise_java import EnterpriseJavaAdapter

            adapters.append(EnterpriseJavaAdapter())
        elif normalized in {"python", "py", "python-ast"}:
            from driftkb.adapters.python import PythonAstAdapter

            adapters.append(PythonAstAdapter())
        else:
            plugin = _load_plugin_adapter(name)
            if plugin is None:
                unknown.append(name)
            else:
                adapters.append(plugin)
    if unknown:
        raise ValueError(f"unknown adapter(s): {', '.join(sorted(unknown))}")
    if not adapters:
        adapters.append(GenericAdapter())
    return tuple(adapters)


def _load_plugin_adapter(name: str) -> FingerprintAdapter | None:
    for entry_point in _adapter_entry_points():
        if entry_point.name.lower() != name.lower():
            continue
        loaded = entry_point.load()
        adapter = loaded() if isinstance(loaded, type) else loaded
        _validate_adapter(name, adapter)
        return adapter
    return None


def _adapter_entry_points() -> tuple[EntryPoint, ...]:
    selected = entry_points(group=ADAPTER_ENTRY_POINT_GROUP)
    return tuple(selected)


def _validate_adapter(name: str, adapter: object) -> None:
    if not hasattr(adapter, "supports") or not hasattr(adapter, "extract"):
        raise ValueError(f"adapter plugin `{name}` must provide supports(path) and extract(path, source_root)")
