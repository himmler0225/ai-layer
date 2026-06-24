from __future__ import annotations

from typing import Any

from app.config.logger import Logger
from app.ingest.dispatcher.routes import route_tool
from app.ingest.mappers import unwrap_result

logger = Logger.get(__name__)
_HISTORY_MARKER = "\n[Câu hỏi hiện tại]\n"


def _product_hint(task: str) -> str:
    """Lấy câu hỏi hiện tại làm gợi ý sản phẩm cho metadata RAG."""
    question = task.split(_HISTORY_MARKER)[-1].strip() if task else ""
    return question[:120] if question else ""


async def schedule_tool_ingest(
    tool_name: str,
    inputs: dict,
    result: Any,
    *,
    task: str = "",
) -> None:
    """Sau tool call — đẩy job ingest nếu crawl thành công."""
    data = unwrap_result(result)
    if data is None:
        return

    platform = "tiktok" if tool_name.startswith("tiktok_") else "youtube"
    try:
        await route_tool(
            tool_name,
            inputs,
            data,
            product_hint=_product_hint(task),
            platform=platform,
        )
    except Exception as exc:
        logger.warning("[ingest] schedule failed tool=%s: %s", tool_name, exc)