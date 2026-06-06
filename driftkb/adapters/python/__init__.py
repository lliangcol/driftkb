from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from driftkb.adapters.base import Fingerprint


class PythonAstAdapter:
    name = "python"

    def supports(self, path: Path) -> bool:
        return path.is_file() and path.suffix.lower() == ".py"

    def extract(self, path: Path, source_root: Path) -> Fingerprint:
        source = path.read_text(encoding="utf-8")
        relative = path.resolve().relative_to(source_root.resolve()).as_posix()
        module = _module_name(relative)
        tree = ast.parse(source)

        imports: set[str] = set()
        symbols: set[str] = {module}
        decorators: set[str] = set()
        classes: list[str] = []
        functions: list[str] = []
        methods: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module_name = "." * node.level + (node.module or "")
                imports.add(module_name)
            elif isinstance(node, ast.ClassDef):
                qualified = f"{module}.{node.name}"
                classes.append(qualified)
                symbols.add(qualified)
                decorators.update(_decorator_name(item) for item in node.decorator_list)
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method = f"{qualified}.{item.name}"
                        methods.append(method)
                        symbols.add(method)
                        decorators.update(_decorator_name(decorator) for decorator in item.decorator_list)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualified = f"{module}.{node.name}"
                functions.append(qualified)
                symbols.add(qualified)
                decorators.update(_decorator_name(item) for item in node.decorator_list)

        annotations = tuple(sorted(f"@{item}" for item in decorators if item))
        semantic_payload = _semantic_payload(
            module=module,
            classes=tuple(sorted(classes)),
            functions=tuple(sorted(functions)),
            methods=tuple(sorted(methods)),
            imports=tuple(sorted(imports)),
            annotations=annotations,
        )
        return Fingerprint(
            adapter=self.name,
            file=relative,
            symbols=tuple(sorted(symbols)),
            annotations=annotations,
            imports=tuple(sorted(imports)),
            raw_hash=hashlib.sha256(source.encode("utf-8")).hexdigest(),
            semantic_hash=hashlib.sha256(semantic_payload.encode("utf-8")).hexdigest(),
            metadata={
                "module": module,
                "classes": tuple(sorted(classes)),
                "functions": tuple(sorted(functions)),
                "methods": tuple(sorted(methods)),
            },
        )


def _module_name(relative_path: str) -> str:
    without_suffix = relative_path.removesuffix(".py")
    parts = [part for part in without_suffix.split("/") if part != "__init__"]
    return ".".join(parts) or "__init__"


def _decorator_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _decorator_name(node.value)
        return f"{owner}.{node.attr}" if owner else node.attr
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return ""


def _semantic_payload(
    *,
    module: str,
    classes: tuple[str, ...],
    functions: tuple[str, ...],
    methods: tuple[str, ...],
    imports: tuple[str, ...],
    annotations: tuple[str, ...],
) -> str:
    return "\n".join(
        (
            f"module:{module}",
            *[f"class:{item}" for item in classes],
            *[f"function:{item}" for item in functions],
            *[f"method:{item}" for item in methods],
            *[f"import:{item}" for item in imports],
            *[f"annotation:{item}" for item in annotations],
        )
    )
