from __future__ import annotations

from typing import Dict, List, Optional

from app.config.logger import Logger
from app.services.agent.constants import HISTORY_MARKER, _TIKTOK, _YOUTUBE

logger = Logger.get(__name__)


def current_question(task: str) -> str:
    """Lấy câu hỏi hiện tại (bỏ phần lịch sử)."""
    if HISTORY_MARKER in task:
        return task.split(HISTORY_MARKER)[-1]
    return task


def detect_platform(task: str) -> Optional[str]:
    """Đoán nền tảng từ từ khóa trong câu hỏi."""
    question = current_question(task)
    has_tiktok = bool(_TIKTOK.search(question))
    has_youtube = bool(_YOUTUBE.search(question))
    if has_tiktok and not has_youtube:
        return "tiktok"
    if has_youtube and not has_tiktok:
        return "youtube"
    return None


def filter_tools_by_platform(tools: List[Dict], task: str) -> List[Dict]:
    """Ẩn tool của nền tảng không liên quan (vd. hỏi YouTube → bỏ tiktok_*)."""
    platform = detect_platform(task)
    if platform is None:
        return tools

    blocked = "tiktok_" if platform == "youtube" else "youtube_"
    filtered = [t for t in tools if not t.get("name", "").startswith(blocked)]

    if len(filtered) != len(tools):
        logger.info(
            "[agent] platform=%s blocked=%s* tools=%d/%d",
            platform, blocked, len(filtered), len(tools),
        )
    return filtered
