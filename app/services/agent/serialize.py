from __future__ import annotations
import json
from typing import Any, Dict
from app.services.agent import config

def serialize_result(result: Any) -> str:
    if not isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False, default=str)[:config.max_result_chars()]
    data = dict(result)
    if 'comments' in data and isinstance(data['comments'], list):
        data['comments'] = [{**c, 'content': (c.get('content') or c.get('text') or '')[:config.max_comment_len()]} for c in data['comments'][:config.max_comments()]]
    for key in ('videos', 'products', 'results', 'items'):
        if key in data and isinstance(data[key], list):
            trimmed = []
            for item in data[key][:config.max_list_items()]:
                if isinstance(item, dict) and 'description' in item:
                    item = {**item, 'description': (item['description'] or '')[:200]}
                trimmed.append(item)
            data[key] = trimmed
    serialized = json.dumps(data, ensure_ascii=False, default=str)
    if len(serialized) > config.max_result_chars():
        serialized = serialized[:config.max_result_chars()] + '... [truncated]"}'
    return serialized
