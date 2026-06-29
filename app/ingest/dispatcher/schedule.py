from __future__ import annotations
from typing import Any
from app.config.logger import Logger
from app.ingest.dispatcher.routes import route_tool
from app.ingest.mappers.unwrap import unwrap_result
from app.rag.product_hint import extract_product_name
logger = Logger.get(__name__)

def _product_hint(task: str) -> str:
    name = extract_product_name(task)
    return name[:120] if name else ''

async def schedule_tool_ingest(tool_name: str, inputs: dict, result: Any, *, task: str='') -> None:
    data = unwrap_result(result)
    if data is None:
        return
    platform = 'tiktok' if tool_name.startswith('tiktok_') else 'youtube'
    try:
        await route_tool(tool_name, inputs, data, product_hint=_product_hint(task), platform=platform)
    except Exception as exc:
        logger.warning('[ingest] schedule failed tool=%s: %s', tool_name, exc)
