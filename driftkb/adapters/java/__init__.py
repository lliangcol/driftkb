from __future__ import annotations

import hashlib
import re
from pathlib import Path

from driftkb.adapters.base import Fingerprint

_PACKAGE_RE = re.compile(r"^\s*package\s+([A-Za-z_][\w.]*)\s*;", re.MULTILINE)
_IMPORT_RE = re.compile(r"^\s*import\s+(?:static\s+)?([A-Za-z_][\w.*]*)\s*;", re.MULTILINE)
_TYPE_RE = re.compile(r"\b(?:public|protected|private|abstract|final|static|\s)*\b(class|interface|enum)\s+([A-Za-z_]\w*)")
_ANNOTATION_RE = re.compile(r"@([A-Za-z_][\w.]*)(?:\s*\(([^)]*)\))?")
_METHOD_RE = re.compile(
    r"\b(?:public|protected)\s+(?:static\s+)?(?:final\s+)?(?:<[^>]+>\s+)?[\w<>\[\].?,\s]+\s+([A-Za-z_]\w*)\s*\([^;{}]*\)\s*(?:throws\s+[^{]+)?\{",
    re.MULTILINE,
)


class JavaRegexAdapter:
    name = "java"

    def supports(self, path: Path) -> bool:
        return path.is_file() and path.suffix.lower() == ".java"

    def extract(self, path: Path, source_root: Path) -> Fingerprint:
        source = path.read_text(encoding="utf-8")
        relative = path.resolve().relative_to(source_root.resolve()).as_posix()
        package = _first_group(_PACKAGE_RE, source)
        types = tuple(sorted(match.group(2) for match in _TYPE_RE.finditer(source)))
        fqcn = tuple(f"{package}.{name}" if package else name for name in types)
        annotations = tuple(sorted(_annotation_text(match) for match in _ANNOTATION_RE.finditer(source)))
        imports = tuple(sorted(set(_IMPORT_RE.findall(source))))
        methods = tuple(sorted(set(_METHOD_RE.findall(source))))
        semantic_payload = "\n".join(
            (
                f"package:{package or ''}",
                *[f"type:{item}" for item in fqcn],
                *[f"annotation:{item}" for item in annotations],
                *[f"import:{item}" for item in imports],
                *[f"method:{item}" for item in methods],
            )
        )
        raw_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
        semantic_hash = hashlib.sha256(semantic_payload.encode("utf-8")).hexdigest()
        return Fingerprint(
            adapter=self.name,
            file=relative,
            symbols=tuple(sorted((*fqcn, *methods))),
            annotations=annotations,
            imports=imports,
            raw_hash=raw_hash,
            semantic_hash=semantic_hash,
            metadata={
                "package": package,
                "types": types,
                "fqcn": fqcn,
                "methods": methods,
            },
        )


def _first_group(pattern: re.Pattern[str], source: str) -> str | None:
    match = pattern.search(source)
    return match.group(1) if match else None


def _annotation_text(match: re.Match[str]) -> str:
    name = match.group(1)
    args = (match.group(2) or "").strip()
    return f"@{name}({args})" if args else f"@{name}"
