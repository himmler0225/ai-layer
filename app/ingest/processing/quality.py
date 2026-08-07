import re

_MIN_LEN = 6
_SPAM_RE = re.compile("^(subscribe|like and subscribe|first!|nice video)\\.?$", re.I)


def is_indexable_comment(text: str) -> bool:
    """Check whether a comment is worth indexing for embeddings/RAG.

    Rejects comments shorter than `_MIN_LEN` characters, comments matching common
    spam/boilerplate phrases (e.g. "subscribe", "first!"), and comments with fewer
    than 3 alphanumeric characters.

    Args:
        text: Comment text to check.

    Returns:
        True if the comment passes all quality checks, False otherwise.
    """
    cleaned = (text or "").strip()
    if len(cleaned) < _MIN_LEN:
        return False
    if _SPAM_RE.match(cleaned):
        return False
    alnum = sum(1 for c in cleaned if c.isalnum())
    return alnum >= 3
