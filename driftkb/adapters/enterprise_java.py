from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from driftkb.adapters.base import Fingerprint
from driftkb.adapters.java import JavaRegexAdapter, build_java_semantic_payload

_ROCKETMQ_SENDER_RE = re.compile(
    r"\b([A-Za-z_]\w*(?:[Rr]ocket[A-Za-z0-9_]*|MQTemplate|MqTemplate|mqTemplate|rocketMQTemplate))"
    r"\s*\.\s*(syncSend|asyncSend|sendOneWay|convertAndSend|sendMessageInTransaction)\s*\((.*?)\)",
    re.DOTALL,
)
_LOGIC_EXCEPTION_RE = re.compile(
    r"\b(?:throw\s+)?new\s+LogicException\s*\(\s*(DomainError\s*\.\s*[A-Za-z_]\w*)",
    re.DOTALL,
)


class EnterpriseJavaAdapter:
    name = "enterprise-java"

    def __init__(self) -> None:
        self._java = JavaRegexAdapter()

    def supports(self, path: Path) -> bool:
        return self._java.supports(path)

    def extract(self, path: Path, source_root: Path) -> Fingerprint:
        source = path.read_text(encoding="utf-8")
        base = self._java.extract(path, source_root)
        metadata = dict(base.metadata)
        risk_fingerprints = _extract_risk_fingerprints(source, base)
        metadata["risk_fingerprints"] = risk_fingerprints

        semantic_payload = "\n".join(
            (
                build_java_semantic_payload(
                    _optional_str(metadata.get("package")),
                    _string_tuple(metadata.get("fqcn")),
                    base.annotations,
                    base.imports,
                    _string_tuple(metadata.get("methods")),
                ),
                "enterprise-java-risk:",
                json.dumps(risk_fingerprints, sort_keys=True, separators=(",", ":")),
            )
        )
        return Fingerprint(
            adapter=self.name,
            file=base.file,
            symbols=base.symbols,
            annotations=base.annotations,
            imports=base.imports,
            raw_hash=base.raw_hash,
            semantic_hash=hashlib.sha256(semantic_payload.encode("utf-8")).hexdigest(),
            metadata=metadata,
        )


def _extract_risk_fingerprints(source: str, fingerprint: Fingerprint) -> dict[str, Any]:
    annotations = fingerprint.annotations
    return {
        "fqcn": list(_string_tuple(fingerprint.metadata.get("fqcn"))),
        "ds": _annotations_named(annotations, "DS"),
        "transactional": _annotations_named(annotations, "Transactional"),
        "rocketmq_listeners": _annotations_named(annotations, "RocketMQMessageListener"),
        "rocketmq_senders": _rocketmq_senders(source),
        "xxl_jobs": _annotations_named(annotations, "XxlJob"),
        "logic_exceptions": _logic_exceptions(source),
    }


def _annotations_named(annotations: tuple[str, ...], short_name: str) -> list[str]:
    return [annotation for annotation in annotations if _annotation_name(annotation) == short_name]


def _annotation_name(annotation: str) -> str:
    return annotation.strip().removeprefix("@").split("(", 1)[0].rsplit(".", 1)[-1]


def _rocketmq_senders(source: str) -> list[dict[str, str]]:
    senders: list[dict[str, str]] = []
    for match in _ROCKETMQ_SENDER_RE.finditer(source):
        senders.append(
            {
                "target": match.group(1),
                "method": match.group(2),
                "args": _normalize_expression(match.group(3)),
            }
        )
    return sorted(senders, key=lambda item: (item["target"], item["method"], item["args"]))


def _logic_exceptions(source: str) -> list[str]:
    errors = {_normalize_expression(match.group(1)) for match in _LOGIC_EXCEPTION_RE.finditer(source)}
    return sorted(errors)


def _normalize_expression(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _string_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, tuple) and all(isinstance(item, str) for item in value):
        return value
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return tuple(value)
    return ()
