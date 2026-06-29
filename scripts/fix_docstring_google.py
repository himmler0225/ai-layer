#!/usr/bin/env python3
"""Chuẩn hóa Args/Returns trong docstring Google Style."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "app"


def _iter_docstrings(tree: ast.AST) -> list[str]:
    docs: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            continue
        if not node.body:
            continue
        first = node.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            docs.append(first.value.value)
    return docs


def _normalize(text: str) -> str | None:
    if "Args:" not in text and "Returns:" not in text:
        return None
    out: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            out.append("")
            continue
        if stripped in {"Args:", "Returns:"}:
            out.append(stripped)
        elif stripped.startswith("(") or "Tham số" in stripped or "Kết quả" in stripped:
            out.append(f"    {stripped}")
        else:
            out.append(stripped)
    result = "\n".join(out).strip("\n")
    return result if result != text else None


def process_file(path: Path) -> int:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    count = 0
    updated = source
    for old in _iter_docstrings(tree):
        new = _normalize(old)
        if not new:
            continue
        updated = updated.replace(f'"""{old}"""', f'"""{new}"""', 1)
        updated = updated.replace(f"'''{old}'''", f"'''{new}'''", 1)
        count += 1
    if count:
        path.write_text(updated, encoding="utf-8")
    return count


def main() -> None:
    total = sum(process_file(p) for p in sorted(ROOT.rglob("*.py")))
    print(f"normalized {total} docstrings")


if __name__ == "__main__":
    main()
