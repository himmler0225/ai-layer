from __future__ import annotations

"""Ghi log agent/tool vào MongoDB (tùy chọn)."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import motor.motor_asyncio
import app.config.settings as _cfg
from app.config.logger import Logger

logger = Logger.get(__name__)

_client: Optional[motor.motor_asyncio.AsyncIOMotorClient] = None


def _db():
    """Lấy database MongoDB (None nếu chưa cấu hình)."""
    global _client
    if not _cfg.MONGODB_URL:
        return None
    if _client is None:
        _client = motor.motor_asyncio.AsyncIOMotorClient(_cfg.MONGODB_URL)
        logger.info("[mongo] client ready db=%s", _cfg.MONGODB_NAME)
    return _client[_cfg.MONGODB_NAME]


async def close_mongo() -> None:
    """Đóng kết nối MongoDB."""
    global _client
    if _client:
        _client.close()
        _client = None


async def log_tool_call(
    session_id: str,
    task: str,
    tool: str,
    inputs: Dict[str, Any],
    result: Any,
    iteration: int,
) -> None:
    """Ghi log một lần gọi tool."""
    db = _db()
    if db is None:
        return
    try:
        await db.tool_logs.insert_one({
            "session_id": session_id,
            "task":       task[:500],
            "tool":       tool,
            "inputs":     inputs,
            "result":     _trim(result),
            "iteration":  iteration,
            "created_at": datetime.now(timezone.utc),
        })
    except Exception as exc:
        logger.warning("[mongo] log_tool_call failed: %s", exc)


async def log_agent_run(
    session_id: str,
    task: str,
    iterations: int,
    tool_calls: List[Dict],
    result_text: str,
    sources: List[Dict],
    videos: List[Dict],
    reviews_analyzed: int,
) -> None:
    """Ghi log một lần chạy agent hoàn tất."""
    db = _db()
    if db is None:
        return
    try:
        await db.agent_logs.insert_one({
            "session_id":       session_id,
            "task":             task[:500],
            "iterations":       iterations,
            "tools_used":       [c["tool"] for c in tool_calls],
            "result_text":      result_text[:2000],
            "sources":          sources,
            "videos":           videos,
            "reviews_analyzed": reviews_analyzed,
            "created_at":       datetime.now(timezone.utc),
        })
    except Exception as exc:
        logger.warning("[mongo] log_agent_run failed: %s", exc)


def _trim(obj: Any, max_len: int = 5000) -> Any:
    """Cắt object log để không vượt giới hạn MongoDB."""
    if isinstance(obj, dict):
        return {k: _trim(v, max_len // max(len(obj), 1)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_trim(i, max_len // max(len(obj), 1)) for i in obj[:50]]
    if isinstance(obj, str) and len(obj) > max_len:
        return obj[:max_len] + "…"
    return obj