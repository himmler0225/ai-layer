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
    r"\bmuốn xem (?:một |1 )?phim\b|"
    r"\b(?:cho|đề xuất)\s+xem phim\b|"
    r"\bphim\s+(?:hàn|trung|mỹ|nhật|thái|việt|anh|pháp|đài|ấn)\b|"
    r"\bphim\s+\S+.*(?:tình cảm|hành động|kinh dị|hài|viễn tưởng|hoạt hình|lãng mạn|"
    r"phiêu lưu|tâm lý|bí ẩn|gia đình)\b|"
    r"\b(?:tình cảm|hành động|kinh dị|hài|lãng mạn)\b.*\bphim\b"
    r")",
    re.IGNORECASE,
)
_COUNTRY_PHIM = re.compile(
    r"phim\b.*\b(?:của\s+)?(?:trung(?:\s*quốc)?|hàn(?:\s*quốc)?|mỹ|nhật|việt|thái|đài|ấn)\b",
    re.IGNORECASE,
)
_TOPIC_HINTS = ("phim", "video", "youtube", "tiktok", "review", "bình luận", "comment", "resident")


def _movie_block(task: str) -> str:
    text = task or ""
    for marker in (MOVIE_BLOCK_MARKER, _LEGACY_PRODUCT_BLOCK):
        if marker in text:
            block = text.split(marker, 1)[1]
            if HISTORY_MARKER in block:
                block = block.split(HISTORY_MARKER, 1)[0]
            return block
    return ""


def conversation_history(task: str) -> str:
    text = task or ""
    if CHAT_HISTORY_BLOCK not in text:
        return ""
    block = text.split(CHAT_HISTORY_BLOCK, 1)[1]
    if HISTORY_MARKER in block:
        block = block.split(HISTORY_MARKER, 1)[0]
    return block.strip()


def current_question(task: str) -> str:
    if HISTORY_MARKER in task:
        return task.split(HISTORY_MARKER)[-1].strip()
    return (task or "").strip()


def is_short_followup(question: str) -> bool:
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
    """Văn bản dùng lọc tool — gộp lịch sử khi câu hiện tại là follow-up ngắn."""
    question = current_question(task)
    history = conversation_history(task)
    if history and is_short_followup(question):
        return f"{history}\n\n{question}"
    if HISTORY_MARKER in (task or ""):
        return question
    return task or ""


def wants_raw_comments(text: str) -> bool:
    return bool(_RAW_COMMENTS_INTENT.search(text or ""))


def wants_review(text: str) -> bool:
    return bool(_REVIEW_INTENT.search(text or ""))


def wants_catalog(text: str) -> bool:
    t = text or ""
    if _CATALOG_INTENT.search(t) or _COUNTRY_PHIM.search(t):
        return True
    if re.search(r"muốn xem.*(?:trung|hàn|mỹ|tình cảm|hành động)", t, re.IGNORECASE):
        return True
    return False


def extract_youtube_video_id(text: str) -> str:
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
    if wants_raw_comments(text):
        return "raw_comments"
    if wants_review(text):
        return "review"
    if wants_catalog(text):
        return "catalog"
    return None


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
    history = conversation_history(task)
    if history:
        for pattern in (_REVIEW_QUOTED, _WATCHING_PREFIX, _MOVIE_MENTION):
            match = pattern.search(history)
            if match:
                return match.group(1).strip()
    return ""


def has_movie_context(task: str) -> bool:
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
    """Thêm hint có cấu trúc khi user follow-up ngắn (Lấy đi, tiếp đi…)."""
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
