import json
from typing import Any
from app.services.agent import config


def serialize_result(result: Any) -> str:
    """Serialize a tool result to a size-capped JSON string, trimming comments/lists/descriptions.

    Non-dict results are JSON-dumped and truncated directly. Dict results have
    their "comments" list capped and each comment's text truncated, and their
    "videos"/"products"/"results"/"items" lists capped with descriptions
    shortened, before being JSON-dumped and truncated to the configured max
    result length.

    Args:
        result: (Any) Raw tool call result to serialize.

    Returns:
        (str) JSON string of the (possibly trimmed) result, truncated to
        config.max_result_chars() with a "... [truncated]" marker if it was cut."""
    if not isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False, default=str)[: config.max_result_chars()]
    data = dict(result)
    if "comments" in data and isinstance(data["comments"], list):
        data["comments"] = [
            {**c, "content": (c.get("content") or c.get("text") or "")[: config.max_comment_len()]}
            for c in data["comments"][: config.max_comments()]
        ]
    for key in ("videos", "products", "results", "items"):
        if key in data and isinstance(data[key], list):
            trimmed = []
            for item in data[key][: config.max_list_items()]:
                if isinstance(item, dict) and "description" in item:
                    item = {**item, "description": (item["description"] or "")[:200]}
                trimmed.append(item)
            data[key] = trimmed
    serialized = json.dumps(data, ensure_ascii=False, default=str)
    if len(serialized) > config.max_result_chars():
        serialized = serialized[: config.max_result_chars()] + '... [truncated]"}'
    return serialized
