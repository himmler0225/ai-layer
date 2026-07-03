import re
import app.services.prompts as _prompts
from app.ai.router import TASK_REVIEW_SUMMARY, max_tokens_for_task, resolve
from app.services.agent.synthesis import _should_fallback_synth, models_with_fallback
from app.utils.llm_errors import log_error
from app.rag.movie_hint import extract_movie_name
from app.config.logger import Logger
from app.utils.llm_responses import create_response, extract_response_text

logger = Logger.get(__name__)
_HISTORY_MARKER = "\n[Câu hỏi hiện tại]\n"
_VIET_RE = re.compile("[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", re.IGNORECASE)
_EMOJI_ONLY_RE = re.compile("^[\\s\\U0001F300-\\U0001FAFF\\U00002600-\\U000027BF\\U0000FE00-\\U0000FEFF!?.…,]+$")
_COMMERCE_RE = re.compile(
    "\\b(giá|pin|sạc|bh|bảo hành|shop|mua|bán|xài|dùng|chất|ok|oke|xịn|keng|body|màn|active|trả|vn/a|like new)\\b",
    re.IGNORECASE,
)
_FOREIGN_RE = re.compile("\\b(perai|mesmo|tamanho|gimana|bagus|sangat|kenapa|kak|anh|bro)\\b", re.IGNORECASE)
_MOVIE_STOPWORDS = frozenset(
    {
        "review",
        "cho",
        "mình",
        "biết",
        "về",
        "của",
        "the",
        "người",
        "dùng",
        "nói",
        "gì",
        "là",
        "có",
        "không",
        "như",
        "thế",
        "nào",
        "phim",
        "movie",
    }
)


def _clean_summary(text: str) -> str:
    """(Nội bộ) Clean summary.

    Args:
        text: (str) Tham số `text`.

    Returns:
        (str) Kết quả trả về."""
    lines: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            lines.append("")
            continue
        if s.startswith(">"):
            continue
        if s.startswith('"') and s.endswith('"') and (len(s) > 40):
            continue
        if s.startswith("📱") or s.startswith("📊") or s.startswith("💬"):
            s = re.sub("^[📱📊💬]\\s*", "", s)
            s = re.sub("\\(\\d+\\s+lượt.*\\)$", "", s).strip()
        lines.append(s)
    out = "\n".join(lines)
    out = re.sub("\\n{3,}", "\n\n", out).strip()
    return out


def _movie_hint(task: str, fallback: str) -> str:
    """(Nội bộ) Product hint.

    Args:
        task: (str) Tham số `task`.
        fallback: (str) Tham số `fallback`.

    Returns:
        (str) Kết quả trả về."""
    from_block = extract_movie_name(task)
    if from_block:
        return from_block
    question = task.split(_HISTORY_MARKER)[-1].strip() if task else ""
    for pattern in (
        "về\\s+(.+?)(?:\\?|$)",
        "review\\s+(.+?)(?:\\?|$)",
        "đánh giá\\s+(.+?)(?:\\?|$)",
        "phân tích\\s+(.+?)(?:\\?|$)",
    ):
        match = re.search(pattern, question, re.IGNORECASE)
        if match:
            hint = match.group(1).strip(" \"'")
            if 3 <= len(hint) <= 80:
                return hint
    for prefix in ("review ", "đánh giá ", "tìm hiểu ", "phân tích "):
        if question.lower().startswith(prefix):
            question = question[len(prefix) :].strip()
    if question and len(question) <= 120:
        return question
    return fallback or "phim"


def _movie_tokens(movie: str) -> list[str]:
    tokens = re.findall("[a-z0-9]{2,}", movie.lower())
    return [t for t in tokens if t not in _MOVIE_STOPWORDS]


def _is_viet_or_english(text: str) -> bool:
    """(Nội bộ) Is viet or english.

    Args:
        text: (str) Tham số `text`.

    Returns:
        (bool) Kết quả trả về."""
    if _VIET_RE.search(text):
        return True
    letters = re.findall("[a-zA-Z]", text)
    return len(letters) >= max(4, len(text.strip()) * 0.4)


def _is_noise(text: str) -> bool:
    """(Nội bộ) Is noise.

    Args:
        text: (str) Tham số `text`.

    Returns:
        (bool) Kết quả trả về."""
    stripped = text.strip()
    if len(stripped) < 6:
        return True
    if _EMOJI_ONLY_RE.match(stripped):
        return True
    return False


def filter_reviews(reviews: list[dict], movie: str) -> list[dict]:
    tokens = _movie_tokens(movie)
    filtered: list[dict] = []
    for review in reviews:
        text = (review.get("content") or review.get("comment") or review.get("text") or "").strip()
        if not text or _is_noise(text):
            continue
        if not _is_viet_or_english(text):
            continue
        if _FOREIGN_RE.search(text) and (not _VIET_RE.search(text)):
            continue
        lower = text.lower()
        matches_movie = tokens and any(token in lower for token in tokens)
        matches_topic = bool(_COMMERCE_RE.search(lower))
        if tokens and (not matches_movie) and (not matches_topic):
            continue
        filtered.append({**review, "content": text})
    return filtered


def _format_reviews(reviews: list[dict]) -> str:
    """(Nội bộ) Định dạng reviews.

    Args:
        reviews: (List[Dict]) Tham số `reviews`.

    Returns:
        (str) Kết quả trả về."""
    lines = []
    for i, review in enumerate(reviews[:120], 1):
        text = review.get("content") or review.get("comment") or review.get("text") or ""
        platform = review.get("platform", "")
        rating = review.get("rating") or review.get("stars")
        if not text:
            continue
        prefix = f"[{rating}★] " if rating else ""
        source_tag = f" [{platform}]" if platform else ""
        lines.append(f"{i}. {prefix}{text[:300]}{source_tag}")
    return "\n".join(lines)


async def summarize_reviews(reviews: list[dict], movie: str = "", source: str = "", task: str = "") -> str | None:
    if not reviews:
        return None
    movie_hint = _movie_hint(task, movie)
    relevant = filter_reviews(reviews, movie_hint)
    if not relevant:
        relevant = [r for r in reviews if (r.get("content") or "").strip()][:40]
    if not (_prompts.REVIEW_SUMMARY_SYSTEM or "").strip():
        return None
    if not (_prompts.REVIEW_SUMMARY_PROMPT or "").strip():
        return None
    prompt = _prompts.REVIEW_SUMMARY_PROMPT.format(
        n=len(relevant), movie=movie_hint, product=movie_hint, source=source, reviews=_format_reviews(relevant)
    )
    _, primary = resolve(TASK_REVIEW_SUMMARY)
    last_exc: Exception | None = None
    for model in models_with_fallback(primary):
        try:
            response = await create_response(
                task=TASK_REVIEW_SUMMARY,
                model=model,
                instructions=_prompts.REVIEW_SUMMARY_SYSTEM,
                input=prompt,
                max_output_tokens=max_tokens_for_task(TASK_REVIEW_SUMMARY),
            )
            raw = extract_response_text(response)
            if not raw:
                return None
            cleaned = _clean_summary(raw.strip())
            return cleaned or None
        except Exception as exc:
            last_exc = exc
            if _should_fallback_synth(exc, model):
                logger.warning(
                    "[review_summary] fallback model=%s after upstream error",
                    model,
                )
                continue
            log_error(logger, exc, where="review_summary")
            return None
    if last_exc:
        log_error(logger, last_exc, where="review_summary")
    return None
