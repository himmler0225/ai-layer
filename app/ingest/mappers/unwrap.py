from __future__ import annotations
from typing import Any

def unwrap_result(result: Any) -> dict | None:
    """Unwrap result.

    Args:
        result: (Any) Tham số `result`.

    Returns:
        (dict | None) Kết quả trả về."""
    if not isinstance(result, dict):
        return None
    if result.get('success') is False:
        return None
    if 'success' in result and 'data' in result:
        inner = result['data']
        if isinstance(inner, dict):
            return inner
        if isinstance(inner, list):
            return {'_list': inner}
        return None
    if result.get('error'):
        return None
    return result

def extract_search_query(inputs: dict) -> str:
    """Trích xuất search query.

    Args:
        inputs: (dict) Tham số `inputs`.

    Returns:
        (str) Kết quả trả về."""
    return (inputs.get('keyword') or inputs.get('query') or inputs.get('topic') or '').strip()

def video_list(data: dict) -> list[dict]:
    """Video list.

    Args:
        data: (dict) Tham số `data`.

    Returns:
        (list[dict]) Kết quả trả về."""
    for key in ('_list', 'results', 'videos', 'items'):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []
