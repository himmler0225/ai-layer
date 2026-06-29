#!/usr/bin/env python3
"""Thêm docstring Google Style (tiếng Việt) cho hàm/class chưa có docstring."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1] / "app"

_SPECIAL_METHODS: dict[str, str] = {
    "__init__": "Khởi tạo instance.",
    "__call__": "Cho phép gọi instance như một hàm.",
    "__aenter__": "Vào async context manager.",
    "__aexit__": "Thoát async context manager.",
    "__aenter__": "Vào async context manager.",
    "__repr__": "Trả về chuỗi mô tả instance.",
    "__str__": "Trả về chuỗi hiển thị của instance.",
    "__iter__": "Trả về iterator.",
    "__aiter__": "Trả về async iterator.",
    "__getattr__": "Ủy quyền đọc attribute khi không tìm thấy trên module.",
}

_VERB_MAP: dict[str, str] = {
    "apply": "Áp dụng",
    "bootstrap": "Khởi tạo",
    "build": "Xây dựng",
    "close": "Đóng",
    "collect": "Thu thập",
    "complete": "Hoàn tất",
    "configure": "Cấu hình",
    "consume": "Tiêu thụ",
    "create": "Tạo",
    "detect": "Phát hiện",
    "emit": "Phát",
    "enrich": "Bổ sung metadata cho",
    "execute": "Thực thi",
    "extract": "Trích xuất",
    "fetch": "Tải",
    "filter": "Lọc",
    "finish": "Hoàn tất",
    "format": "Định dạng",
    "get": "Lấy",
    "handle": "Xử lý",
    "init": "Khởi tạo",
    "invoke": "Gọi",
    "load": "Tải",
    "log": "Ghi log",
    "normalize": "Chuẩn hóa",
    "parse": "Phân tích",
    "prepare": "Chuẩn bị",
    "publish": "Xuất bản",
    "resolve": "Giải quyết",
    "run": "Chạy",
    "schedule": "Lên lịch",
    "search": "Tìm kiếm",
    "setup": "Cấu hình",
    "start": "Bắt đầu",
    "stop": "Dừng",
    "store": "Lưu",
    "summarize": "Tóm tắt",
    "sync": "Đồng bộ",
    "validate": "Kiểm tra",
    "verify": "Xác minh",
    "warm": "Làm nóng",
    "write": "Ghi",
}


def _has_docstring(node: ast.AST) -> bool:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return False
    if not node.body:
        return False
    first = node.body[0]
    return (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    )


def _unparse(node: ast.AST | None) -> str:
    if node is None:
        return "None"
    try:
        return ast.unparse(node)
    except Exception:
        return "Any"


def _human_name(name: str) -> str:
    if name in _SPECIAL_METHODS:
        return _SPECIAL_METHODS[name]
    if name.startswith("__") and name.endswith("__"):
        return f"Hook đặc biệt `{name}`."
    if name.startswith("is_"):
        return f"Kiểm tra {name[3:].replace('_', ' ')}."
    if name.startswith("has_"):
        return f"Kiểm tra có {name[4:].replace('_', ' ')} hay không."
    if name.startswith("new_"):
        return f"Tạo {name[4:].replace('_', ' ')} mới."
    if name.startswith("begin_"):
        return f"Bắt đầu {name[6:].replace('_', ' ')}."
    if name.startswith("end_"):
        return f"Kết thúc {name[4:].replace('_', ' ')}."
    parts = [p for p in name.split("_") if p]
    if not parts:
        return f"Hàm `{name}`."
    verb = parts[0]
    rest = " ".join(parts[1:]) or name
    vi_verb = _VERB_MAP.get(verb, verb.capitalize())
    if len(parts) == 1:
        return f"{vi_verb} `{name}`."
    return f"{vi_verb} {rest.replace('_', ' ')}."


def _arg_lines(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    lines: list[str] = []
    args = list(node.args.args)
    if node.args.vararg:
        args.append(node.args.vararg)
    args.extend(node.args.kwonlyargs)
    if node.args.kwarg:
        args.append(node.args.kwarg)
    defaults_offset = len(args) - len(node.args.defaults)
    for idx, arg in enumerate(args):
        if arg.arg in {"self", "cls", "mcs"}:
            continue
        ann = _unparse(arg.annotation) if arg.annotation else "Any"
        default_note = ""
        if arg in node.args.kwonlyargs:
            kw_idx = node.args.kwonlyargs.index(arg)
            if kw_idx < len(node.args.kw_defaults) and node.args.kw_defaults[kw_idx] is not None:
                default_note = f", mặc định {_unparse(node.args.kw_defaults[kw_idx])}"
        elif idx >= defaults_offset and node.args.defaults:
            d_idx = idx - defaults_offset
            if d_idx < len(node.args.defaults):
                default_note = f", mặc định {_unparse(node.args.defaults[d_idx])}"
        lines.append(f"    {arg.arg}: ({ann}{default_note}) Tham số `{arg.arg}`.")
    return lines


def _build_function_doc(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    summary = _human_name(node.name)
    if node.name.startswith("_") and not node.name.startswith("__"):
        summary = f"(Nội bộ) {summary}"
    if isinstance(node, ast.AsyncFunctionDef):
        summary = summary.rstrip(".") + " (async)."
    lines = [summary, ""]
    arg_lines = _arg_lines(node)
    if arg_lines:
        lines.append("Args:")
        lines.extend(arg_lines)
        lines.append("")
    if node.returns is not None:
        lines.append("Returns:")
        lines.append(f"    ({_unparse(node.returns)}) Kết quả trả về.")
        lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def _build_class_doc(node: ast.ClassDef) -> str:
    bases = ", ".join(_unparse(b) for b in node.bases) if node.bases else "object"
    return f"    Lớp `{node.name}` (kế thừa {bases})."


def _indent_for(node: ast.AST, lines: list[str]) -> str:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return "    "
    if not node.body:
        return " " * (node.col_offset + 4)
    return " " * node.body[0].col_offset


def _docstring_block(indent: str, doc: str) -> list[str]:
    escaped = doc.replace('"""', '\\"\\"\\"')
    inner = escaped.split("\n")
    if len(inner) == 1:
        return [f'{indent}"""{inner[0]}"""\n']
    out = [f'{indent}"""\n']
    for line in inner:
        out.append(f"{indent}{line}\n" if line else f"\n")
    out.append(f'{indent}"""\n')
    return out


def _targets(tree: ast.AST) -> Iterable[ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if _has_docstring(node):
                continue
            if not node.body:
                continue
            yield node


def process_file(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        print(f"skip syntax error {path}: {exc}", file=sys.stderr)
        return False
    lines = source.splitlines(keepends=True)
    nodes = sorted(_targets(tree), key=lambda n: n.end_lineno or n.lineno, reverse=True)
    if not nodes:
        return False
    for node in nodes:
        indent = _indent_for(node, lines)
        if isinstance(node, ast.ClassDef):
            doc = _build_class_doc(node)
        else:
            doc = _build_function_doc(node)
        block = _docstring_block(indent, doc)
        insert_at = node.end_lineno or node.lineno
        lines[insert_at:insert_at] = block
    path.write_text("".join(lines), encoding="utf-8")
    return True


def main() -> None:
    changed = 0
    for path in sorted(ROOT.rglob("*.py")):
        if process_file(path):
            changed += 1
            print(path.relative_to(ROOT.parent))
    print(f"updated {changed} files")


if __name__ == "__main__":
    main()
