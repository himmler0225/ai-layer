from __future__ import annotations
import re
_MIN_LEN = 6
_SPAM_RE = re.compile('^(subscribe|like and subscribe|first!|nice video)\\.?$', re.I)

def is_indexable_comment(text: str) -> bool:
    """Is indexable comment.

    Args:
        text: (str) Tham số `text`.

    Returns:
        (bool) Kết quả trả về."""
    cleaned = (text or '').strip()
    if len(cleaned) < _MIN_LEN:
        return False
    if _SPAM_RE.match(cleaned):
        return False
    alnum = sum((1 for c in cleaned if c.isalnum()))
    return alnum >= 3
