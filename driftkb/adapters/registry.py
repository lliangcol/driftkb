from __future__ import annotations

from driftkb.adapters.base import FingerprintAdapter
from driftkb.adapters.generic import GenericAdapter


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
        else:
            unknown.append(name)
    if unknown:
        raise ValueError(f"unknown adapter(s): {', '.join(sorted(unknown))}")
    if not adapters:
        adapters.append(GenericAdapter())
    return tuple(adapters)
