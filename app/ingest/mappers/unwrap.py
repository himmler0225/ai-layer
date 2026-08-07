from typing import Any


def unwrap_result(result: Any) -> dict | None:
    """Unwrap a tool call's result envelope into a plain data dict.

    Handles the standard {"success": bool, "data": ...} tool result shape: returns
    None on explicit failure, wraps a list payload as {"_list": [...]}, and passes
    a dict payload through unchanged. Non-dict results, results with an "error" key,
    or results with neither "success" nor "data"/"error" markers are also handled.

    Args:
        result: Raw return value of a tool call.

    Returns:
        The unwrapped data dict, or None if the result indicates failure or has no
        usable data.
    """
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
    """Recover the search keyword/query a search tool was called with.

    Args:
        inputs: Original tool call arguments.

    Returns:
        The value of the first present "keyword", "query", or "topic" key, stripped;
        "" if none are present.
    """
    return (inputs.get("keyword") or inputs.get("query") or inputs.get("topic") or "").strip()


def video_list(data: dict) -> list[dict]:
    """Extract the list of raw video dicts from an unwrapped tool result.

    Args:
        data: Unwrapped tool result data, expected to hold a list under one of
            "_list", "results", "videos", or "items".

    Returns:
        The list of dict items found under the first matching key, filtering out
        non-dict entries; [] if none of the keys hold a list.
    """
    for key in ("_list", "results", "videos", "items"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []
