import re
from app.services.agent.constants import HISTORY_MARKER

MOVIE_BLOCK_MARKER = "[Phim đang xem]"
CHAT_HISTORY_BLOCK = "[Lịch sử hội thoại]"
CONTEXT_HINT_BLOCK = "[Ngữ cảnh từ lịch sử]"
_LEGACY_PRODUCT_BLOCK = "[Sản phẩm đang xem]"
_WATCHING_PREFIX = re.compile(r'\[Đang xem phim\s+"([^"]+)"', re.IGNORECASE)
_REVIEW_QUOTED = re.compile(
    r'Review (?:the )?(?:phim|sản phẩm|movie|product)\s+["\u201c]([^"\u201d]+)["\u201d]',
    re.IGNORECASE,
)
_NAME_LINE = re.compile(r"^Tên:\s*(.+)$", re.MULTILINE | re.IGNORECASE)
_MOVIE_MENTION = re.compile(r"(?:phim|movie|film)\s+([^\n,.?!]{2,80})", re.IGNORECASE)
_YOUTUBE_URL = re.compile(
    r"https?://(?:www\.)?(?:youtube\.com/\S+|youtu\.be/\S+)",
    re.IGNORECASE,
)
_VIDEO_ID_LINE = re.compile(r"\bvideo[_\s-]?id[:\s]+([A-Za-z0-9_-]{6,})\b", re.IGNORECASE)
_SHORT_FOLLOWUP = re.compile(
    r"^(?:"
    r"lấy(?:\s+đi|\s+lại)?|tiếp(?:\s+đi|\s+tục)?|làm\s+đi|gửi\s+đi|"
    r"thử\s+lại|lại\s+đi|ok(?:e)?|được|rồi|"
    r"(?:get|fetch)\s+it|continue|go\s+ahead|yes|please|retry"
    r")[\s!.?,]*$",
    re.IGNORECASE,
)
_RAW_COMMENTS_INTENT = re.compile(
    r"\b(?:"
    r"bình luận thô|raw comments?|comment thô|chỉ (?:xem )?bình luận|"
    r"xem bình luận(?: thô)?|lấy bình luận|only comments?|just (?:the )?comments?"
    r")\b",
    re.IGNORECASE,
)
_REVIEW_INTENT = re.compile(
    r"\b(?:review|đánh giá|người dùng nói gì|users?\s+say|nên xem|worth watching)\b",
    re.IGNORECASE,
)
_CATALOG_INTENT = re.compile(
    r"(?:"
    r"\b(?:tìm|gợi ý|recommend)\s+phim\b|"
    r"\bmuốn xem\b.{0,12}?\bphim\b|"
    r"\b(?:cho|đề xuất)\s+xem phim\b|"
    r"\bphim\s+(?:hàn|trung|mỹ|nhật|thái|việt|anh|pháp|đài|ấn)\b|"
    r"\bphim\s+\S+.*(?:tình cảm|hành động|kinh dị|hài|viễn tưởng|hoạt hình|lãng mạn|"
    r"phiêu lưu|tâm lý|bí ẩn|gia đình)\b|"
    r"\b(?:tình cảm|hành động|kinh dị|hài|lãng mạn)\b.*\bphim\b|"
    r"\bphim\b.{0,15}?\b(?:nữa|thêm|khác)\b|"
    r"\b(?:thêm|nhiều)\b.{0,15}?\bphim\b"
    r")",
    re.IGNORECASE,
)
_COUNTRY_PHIM = re.compile(
    r"phim\b.*\b(?:của\s+)?(?:trung(?:\s*quốc)?|hàn(?:\s*quốc)?|mỹ|nhật|việt|thái|đài|ấn)\b",
    re.IGNORECASE,
)
_TOPIC_HINTS = ("phim", "video", "youtube", "tiktok", "review", "bình luận", "comment", "resident")


def _movie_block(task: str) -> str:
    """Extract the "[Phim đang xem]" (or legacy "[Sản phẩm đang xem]") block from a task.

    Args:
        task: Raw task/prompt text that may contain a movie-context block.

    Returns:
        The text following the marker up to the next history marker, or
        an empty string if no such block is present.
    """
    text = task or ""
    for marker in (MOVIE_BLOCK_MARKER, _LEGACY_PRODUCT_BLOCK):
        if marker in text:
            block = text.split(marker, 1)[1]
            if HISTORY_MARKER in block:
                block = block.split(HISTORY_MARKER, 1)[0]
            return block
    return ""


def conversation_history(task: str) -> str:
    """Extract the "[Lịch sử hội thoại]" block from a task, up to the history marker.

    Args:
        task: Raw task/prompt text that may contain a chat-history block.

    Returns:
        The stripped conversation history text, or an empty string if none is present.
    """
    text = task or ""
    if CHAT_HISTORY_BLOCK not in text:
        return ""
    block = text.split(CHAT_HISTORY_BLOCK, 1)[1]
    if HISTORY_MARKER in block:
        block = block.split(HISTORY_MARKER, 1)[0]
    return block.strip()


def current_question(task: str) -> str:
    """Extract the current user question, i.e. the text after the last history marker.

    Args:
        task: Raw task/prompt text, possibly containing history markers.

    Returns:
        The stripped text following the last `HISTORY_MARKER`, or the
        whole (stripped) task if no marker is present.
    """
    if HISTORY_MARKER in task:
        return task.split(HISTORY_MARKER)[-1].strip()
    return (task or "").strip()


def is_short_followup(question: str) -> bool:
    """Heuristically detect whether a question is a short, context-dependent follow-up.

    Matches known short follow-up phrases (e.g. "lấy đi", "continue", "ok")
    or, failing that, treats any question of 4 words or fewer that contains
    none of the topic keywords as a likely follow-up.

    Args:
        question: The current user question to test.

    Returns:
        True if the question looks like a short follow-up needing prior context.
    """
    q = (question or "").strip()
    if not q or len(q) > 35:
        return False
    if _SHORT_FOLLOWUP.match(q):
        return True
    words = q.split()
    if len(words) <= 4 and not any(h in q.lower() for h in _TOPIC_HINTS):
        return True
    return False


def context_for_filtering(task: str) -> str:
    """Build the text used for tool filtering, merging history when the current question is a short follow-up."""
    question = current_question(task)
    history = conversation_history(task)
    if history and is_short_followup(question):
        return f"{history}\n\n{question}"
    if HISTORY_MARKER in (task or ""):
        return question
    return task or ""


def wants_raw_comments(text: str) -> bool:
    """Detect whether the text expresses intent to get raw/unsummarized comments.

    Args:
        text: User text to check.

    Returns:
        True if the text matches the raw-comments intent pattern.
    """
    return bool(_RAW_COMMENTS_INTENT.search(text or ""))


def wants_review(text: str) -> bool:
    """Detect whether the text expresses intent to get a review/opinion summary.

    Args:
        text: User text to check.

    Returns:
        True if the text matches the review intent pattern.
    """
    return bool(_REVIEW_INTENT.search(text or ""))


def wants_catalog(text: str) -> bool:
    """Detect whether the text is asking for a movie catalog/recommendation list.

    Args:
        text: User text to check.

    Returns:
        True if the text matches the catalog intent or country/genre movie patterns.
    """
    t = text or ""
    if _CATALOG_INTENT.search(t) or _COUNTRY_PHIM.search(t):
        return True
    if re.search(r"muốn xem.*(?:trung|hàn|mỹ|tình cảm|hành động)", t, re.IGNORECASE):
        return True
    return False


def extract_youtube_video_id(text: str) -> str:
    """Extract a YouTube video ID from a URL or an explicit "video_id: ..." mention in text.

    Args:
        text: Text that may contain a YouTube URL or a video_id reference.

    Returns:
        The extracted video ID, or an empty string if none is found.
    """
    from app.services.url_extractor import extract_id_from_url

    for url in _YOUTUBE_URL.findall(text or ""):
        result = extract_id_from_url(url)
        vid = result.get("video_id")
        if vid:
            return str(vid)
    match = _VIDEO_ID_LINE.search(text or "")
    if match:
        return match.group(1)
    return ""


def detect_intent(text: str) -> str | None:
    """Classify text into one of the known intents by checking each detector in priority order.

    Args:
        text: User text to classify.

    Returns:
        "raw_comments", "review", or "catalog" if a matching intent is
        detected, otherwise None.
    """
    if wants_raw_comments(text):
        return "raw_comments"
    if wants_review(text):
        return "review"
    if wants_catalog(text):
        return "catalog"
    return None


def extract_movie_name(task: str) -> str:
    """Extract the movie name being discussed from a task's movie block, current text, or history.

    Tries, in order: the "Tên:" line of the movie-context block, the
    "[Đang xem phim ...]" prefix, a quoted "Review ... phim/movie 'X'"
    mention, and finally the same patterns searched over conversation
    history.

    Args:
        task: Raw task/prompt text.

    Returns:
        The extracted movie name, or an empty string if none is found.
    """
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
    history = conversation_history(task)
    if history:
        for pattern in (_REVIEW_QUOTED, _WATCHING_PREFIX, _MOVIE_MENTION):
            match = pattern.search(history)
            if match:
                return match.group(1).strip()
    return ""


def has_movie_context(task: str) -> bool:
    """Determine whether a task has an associated movie in context (current or from history).

    Checks the current task for a movie block, "Đang xem phim" prefix, or
    an extractable movie name; if the current question is a short
    follow-up, also checks conversation history for the same signals.

    Args:
        task: Raw task/prompt text.

    Returns:
        True if a movie is in context for this task.
    """
    text = task or ""
    if MOVIE_BLOCK_MARKER in text or _LEGACY_PRODUCT_BLOCK in text:
        return True
    if _WATCHING_PREFIX.search(text):
        return True
    if extract_movie_name(task):
        return True
    history = conversation_history(task)
    if history and is_short_followup(current_question(task)):
        if MOVIE_BLOCK_MARKER in history or _LEGACY_PRODUCT_BLOCK in history:
            return True
        for pattern in (_REVIEW_QUOTED, _WATCHING_PREFIX, _MOVIE_MENTION):
            if pattern.search(history):
                return True
    return False


def enrich_short_followup_task(task: str) -> str:
    """Prepend a structured context hint block to short follow-up tasks (e.g. "Lấy đi", "tiếp đi...").

    Uses the extracted movie name, YouTube video ID, and detected intent
    from history/question to build hint lines, so downstream tool
    filtering has enough context even though the user's message alone is
    too short.

    Args:
        task: Raw task/prompt text.

    Returns:
        The task with a "[Ngữ cảnh từ lịch sử]" hint block prepended, or
        the original task unchanged if it isn't a short follow-up, has no
        history, has no hints to add, or already has a hint block.
    """
    question = current_question(task)
    if not is_short_followup(question):
        return task
    history = conversation_history(task)
    if not history:
        return task

    combined = f"{history}\n{question}"
    hints: list[str] = []

    movie = extract_movie_name(task)
    if movie:
        hints.append(f"Phim đang thảo luận: {movie}")

    video_id = extract_youtube_video_id(combined)
    if video_id:
        hints.append(f"YouTube video_id: {video_id}")

    intent = detect_intent(history) or detect_intent(question)
    if intent == "raw_comments":
        hints.append("Intent: lấy bình luận thô từ video (YouTube/TikTok), không tóm tắt review")
    elif intent == "review":
        hints.append("Intent: review / đánh giá phim từ nguồn social")

    if not hints:
        return task

    hint_block = CONTEXT_HINT_BLOCK + "\n" + "\n".join(f"- {line}" for line in hints)
    if CONTEXT_HINT_BLOCK in task:
        return task
    return f"{hint_block}\n\n{task}"
