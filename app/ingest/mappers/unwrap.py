from __future__ import annotations

from typing import Any


def unwrap_result(result: Any) -> dict | None:
    """Bóc lớp ApiResponse; trả None nếu crawl thất bại."""
    if not isinstance(result, dict):
        return None
    if result.get("success") is False:
        return None
    if "success" in result and "data" in result:
        inner = result["data"]
        if isinstance(inner, dict):
            return inner
        if isinstance(inner, list):
            return {"_list": inner}
        return None
    if result.get("error"):
        return None
    return result


def extract_search_query(inputs: dict) -> str:
    """Lấy từ khóa search từ input tool."""
    return (
        inputs.get("keyword") or inputs.get("query") or inputs.get("topic") or ""
    ).strip()


def video_list(data: dict) -> list[dict]:
    """Tìm list video trong các key phổ biến của response."""
    for key in ("_list", "results", "videos", "items"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []
