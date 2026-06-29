#!/usr/bin/env python3
"""Sửa thụt lề nội dung docstring Google Style (PEP 257)."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "app"


def _collect(tree: ast.AST) -> list[str]:
    out: list[str] = []
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
            out.append(first.value.value)
    return out


def _fix(text: str) -> str | None:
    if "Args:" not in text and "Returns:" not in text:
        return None
    lines = text.split("\n")
    section: str | None = None
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            out.append("")
            section = section
            continue
        if stripped in {"Args:", "Returns:", "Raises:"}:
            section = stripped
            out.append(f"    {stripped}")
            continue
        if section in {"Args:", "Returns:", "Raises:"}:
            out.append(f"        {stripped}")
            continue
        out.append(stripped)
    result = "\n".join(out)
    return result if result != text else None


def process_file(path: Path) -> int:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    n = 0
    updated = source
    for old in _collect(tree):
        new = _fix(old)
        if not new:
            continue
        updated = updated.replace(f'"""{old}"""', f'"""{new}"""', 1)
        updated = updated.replace(f"'''{old}'''", f"'''{new}'''", 1)
        n += 1
    if n:
        path.write_text(updated, encoding="utf-8")
    return n


def main() -> None:
    total = sum(process_file(p) for p in sorted(ROOT.rglob("*.py")))
    print(f"pep257-fixed {total} docstrings")


if __name__ == "__main__":
    main()
