from __future__ import annotations
import re
from app.services.agent.constants import HISTORY_MARKER
PRODUCT_BLOCK_MARKER = '[Sản phẩm đang xem]'
_REVIEW_QUOTED = re.compile('Review (?:the )?sản phẩm ["\\u201c]([^"\\u201d]+)["\\u201d]|Review the product ["\\u201c]([^"\\u201d]+)["\\u201d]', re.IGNORECASE)
_NAME_LINE = re.compile('^Tên:\\s*(.+)$', re.MULTILINE | re.IGNORECASE)

def current_question(task: str) -> str:
    if HISTORY_MARKER in task:
        return task.split(HISTORY_MARKER)[-1].strip()
    return (task or '').strip()

def extract_product_name(task: str) -> str:
    text = task or ''
    if PRODUCT_BLOCK_MARKER in text:
        block = text.split(PRODUCT_BLOCK_MARKER, 1)[1]
        if HISTORY_MARKER in block:
            block = block.split(HISTORY_MARKER, 1)[0]
        match = _NAME_LINE.search(block)
        if match:
            return match.group(1).strip()
    quoted = _REVIEW_QUOTED.search(text)
    if quoted:
        return (quoted.group(1) or quoted.group(2) or '').strip()
    return ''
