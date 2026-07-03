import re
from app.services.agent.constants import HISTORY_MARKER

MOVIE_BLOCK_MARKER = "[Phim đang xem]"
_LEGACY_PRODUCT_BLOCK = "[Sản phẩm đang xem]"
_WATCHING_PREFIX = re.compile(r'\[Đang xem phim\s+"([^"]+)"', re.IGNORECASE)
_REVIEW_QUOTED = re.compile(
    r'Review (?:the )?(?:phim|sản phẩm|movie|product)\s+["\u201c]([^"\u201d]+)["\u201d]',
    re.IGNORECASE,
)
_NAME_LINE = re.compile(r"^Tên:\s*(.+)$", re.MULTILINE | re.IGNORECASE)


def _movie_block(task: str) -> str:
    text = task or ""
    for marker in (MOVIE_BLOCK_MARKER, _LEGACY_PRODUCT_BLOCK):
        if marker in text:
            block = text.split(marker, 1)[1]
            if HISTORY_MARKER in block:
                block = block.split(HISTORY_MARKER, 1)[0]
            return block
    return ""


def current_question(task: str) -> str:
    if HISTORY_MARKER in task:
        return task.split(HISTORY_MARKER)[-1].strip()
    return (task or "").strip()


def extract_movie_name(task: str) -> str:
    block = _movie_block(task)
    if block:
        match = _NAME_LINE.search(block)
        if match:
            return match.group(1).strip()
    text = task or ""
    watching = _WATCHING_PREFIX.search(text)
    if watching:
        return watching.group(1).strip()
    quoted = _REVIEW_QUOTED.search(text)
    if quoted:
        return quoted.group(1).strip()
    return ""


def has_movie_context(task: str) -> bool:
    text = task or ""
    if MOVIE_BLOCK_MARKER in text or _LEGACY_PRODUCT_BLOCK in text:
        return True
    if _WATCHING_PREFIX.search(text):
        return True
    return bool(extract_movie_name(text))
