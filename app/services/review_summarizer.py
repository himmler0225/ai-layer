import re
import app.services.prompts as _prompts
from app.ai.router import TASK_REVIEW_SUMMARY, max_tokens_for_task, resolve
from app.services.agent.synthesis import _should_fallback_synth, models_with_fallback
from app.utils.llm_errors import log_error
from app.rag.movie_hint import extract_movie_name
from app.config.logger import Logger, log_event
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
    """Strip LLM formatting artifacts from a generated review summary.

    Drops blockquote lines (starting with ">"), drops long lines that are
    entirely wrapped in quotes (likely stray verbatim review quotes), and
    strips leading emoji markers (mobile/chart/chat bubble) along with any
    trailing "(N lượt ...)" annotation on those lines. Collapses runs of 3+
    blank lines down to a single blank line.

    Args:
        text: Raw summary text returned by the LLM.

    Returns:
        The cleaned summary text.
    """
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
    """Infer the movie/product name being asked about, for prompt-building.

    Tries, in order: an explicit movie-name block extracted from `task`
    (via `extract_movie_name`), a regex match on phrases like "về X",
    "review X", "đánh giá X", "phân tích X" in the current question, then
    the question itself with those leading verbs stripped, and finally
    `fallback`.

    Args:
        task: Full task/conversation text (may include prior turns
            separated by the history marker).
        fallback: Value to return if no name could be inferred.

    Returns:
        The inferred movie/product name, or `fallback` (or "phim" if
        `fallback` is also empty).
    """
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
    """Extract lowercase alphanumeric tokens from a movie/product name.

    Used to build a keyword set for matching reviews against the movie
    being discussed. Common stopwords (`_MOVIE_STOPWORDS`) are filtered out.

    Args:
        movie: Movie/product name string.

    Returns:
        List of tokens (2+ chars) with stopwords removed.
    """
    tokens = re.findall("[a-z0-9]{2,}", movie.lower())
    return [t for t in tokens if t not in _MOVIE_STOPWORDS]


def _is_viet_or_english(text: str) -> bool:
    """Heuristically check whether text looks like Vietnamese or English.

    Returns True if the text contains a Vietnamese diacritic, or if Latin
    letters make up at least 40% of its stripped length (min 4 letters).
    Used to filter out reviews written in unrelated languages.

    Args:
        text: Text to check.

    Returns:
        True if the text appears to be Vietnamese or English.
    """
    if _VIET_RE.search(text):
        return True
    letters = re.findall("[a-zA-Z]", text)
    return len(letters) >= max(4, len(text.strip()) * 0.4)


def _is_noise(text: str) -> bool:
    """Check whether a review is too short or emoji-only to be useful.

    Args:
        text: Review text to check.

    Returns:
        True if the stripped text is shorter than 6 characters, or matches
        only emoji/punctuation/whitespace.
    """
    stripped = text.strip()
    if len(stripped) < 6:
        return True
    if _EMOJI_ONLY_RE.match(stripped):
        return True
    return False


def filter_reviews(reviews: list[dict], movie: str) -> list[dict]:
    """Filter raw reviews down to ones relevant to the given movie/product.

    Drops empty/noisy reviews (see `_is_noise`), reviews that aren't
    Vietnamese/English (see `_is_viet_or_english`), and reviews that look
    foreign-language but contain no Vietnamese diacritics. If `movie`
    yields keyword tokens, also drops reviews that mention neither the
    movie's tokens nor a generic commerce-related keyword.

    Args:
        reviews: Raw review dicts, each with a "content"/"comment"/"text"
            field.
        movie: Movie/product name used to derive matching keywords.

    Returns:
        Filtered list of review dicts, each with its "content" field
        normalized to the extracted text.
    """
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
    """Render up to 120 reviews as a numbered list for the LLM prompt.

    Each line includes an optional star-rating prefix and platform tag,
    with review text truncated to 300 characters.

    Args:
        reviews: Review dicts, each with "content"/"comment"/"text",
            optional "platform", and optional "rating"/"stars".

    Returns:
        The formatted, newline-joined list as a single string.
    """
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
    """Generate an LLM summary of collected reviews for a movie/product.

    Filters the reviews for relevance (falling back to the first 40
    non-empty reviews if filtering removes everything), builds the review
    summary prompt, and calls the configured LLM (with model fallback) to
    produce a cleaned summary. Returns None if the prompt templates aren't
    configured, if there are no reviews, or if every candidate model fails.

    Args:
        reviews: Raw review dicts to summarize.
        movie: Movie/product name, used as a fallback hint if none can be
            inferred from `task`.
        source: Label describing where the reviews came from (e.g.
            "YouTube"), inserted into the prompt.
        task: Original task/question text, used to infer the movie name.

    Returns:
        The cleaned summary text, or None if no summary could be produced.
    """
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
                    log_event("review_summary", "model fallback", model=model, reason="upstream_error")
                )
                continue
            log_error(logger, exc, where="review_summary")
            return None
    if last_exc:
        log_error(logger, last_exc, where="review_summary")
    return None
