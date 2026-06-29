#!/usr/bin/env python3
"""Chuẩn hóa thụt lề docstring Google Style (bỏ 4 space thừa)."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "app"


def _docstring_nodes(tree: ast.AST) -> list[ast.Constant]:
    out: list[ast.Constant] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            if not node.body:
                continue
            first = node.body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                out.append(first.value)
    return out


def _normalize_doc(text: str) -> str | None:
    lines = text.split("\n")
    if not lines:
        return None
    # Chỉ sửa khi dòng nội dung (không rỗng) đều thụt >= 4 space so với mức tối thiểu.
    indents = [len(line) - len(line.lstrip()) for line in lines if line.strip()]
    if not indents:
        return None
    min_indent = min(indents)
    if min_indent < 4:
        return None
    # Docstring auto-gen thường thụt thừa 4 space (12 thay vì 8).
    if not all(i >= min_indent + 4 or not line.strip() for line, i in zip(lines, [len(l) - len(l.lstrip()) if l.strip() else min_indent for l in lines])):
        # Chỉ sửa nếu hầu hết dòng có indent >= 8 và có Args/Returns kiểu auto
        if "    Args:" not in text and "        Args:" not in text:
            return None
    fixed: list[str] = []
    changed = False
    for line in lines:
        if line.strip() and line.startswith(" " * 4):
            fixed.append(line[4:])
            changed = True
        else:
            fixed.append(line)
    if not changed:
        return None
    result = "\n".join(fixed)
    while result.endswith("\n\n"):
        result = result[:-1]
    return result


def process_file(path: Path) -> int:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0
    replacements: dict[str, str] = {}
    for const in _docstring_nodes(tree):
        new = _normalize_doc(const.value)
        if new and new != const.value:
            replacements[const.value] = new
    if not replacements:
        return 0
    updated = source
    for old, new in replacements.items():
        updated = updated.replace(f'"""{old}"""', f'"""{new}"""', 1)
        updated = updated.replace(f"'''{old}'''", f"'''{new}'''", 1)
    path.write_text(updated, encoding="utf-8")
    return len(replacements)


def main() -> None:
    total = 0
    for path in sorted(ROOT.rglob("*.py")):
        n = process_file(path)
        if n:
            total += n
            print(f"{path.relative_to(ROOT.parent)}: {n}")
    print(f"fixed {total} docstrings")


if __name__ == "__main__":
    main()
