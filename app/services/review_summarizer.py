import re
from typing import Dict, List, Optional

import app.config.settings as _cfg
from app.utils.openai_responses import create_response, extract_response_text

_SYSTEM = (
    "Bạn là công cụ tổng hợp reviews thương mại điện tử. "
    "Nhiệm vụ duy nhất: cluster theo chủ đề + trích dẫn nguyên văn. "
    "TUYỆT ĐỐI không thêm nhận xét cá nhân, không dùng từ 'tốt'/'xấu'/'tệ'."
)

REVIEW_SUMMARY_PROMPT = """\
Bạn nhận được {n} comments/reviews về "{product}" từ {source}.

Nhiệm vụ:
1. CHỈ nhóm comments LIÊN QUAN đến sản phẩm/chủ đề "{product}" (chất lượng, giá, pin, giao hàng, bảo hành, trải nghiệm dùng...)
2. BỎ QUA hoàn toàn: spam, comment ngoài ngôn ngữ (Indonesia, Bồ Đào Nha, Thái...), meme không liên quan, tag bạn bè
3. Với mỗi chủ đề, trích dẫn NGUYÊN VĂN tối đa 3 comments đại diện
4. Ghi rõ số lượng comments đề cập đến chủ đề đó

Format output (BẮT BUỘC — mỗi trích dẫn một dòng blockquote riêng):

### 📦 Chất lượng sản phẩm (23 lượt đề cập)
> "2 tuần là xanh màn"

> "dùng 3 tháng vẫn tốt, không có vấn đề gì"

### 🚚 Giao hàng (15 lượt đề cập)
> "ship 2 ngày, đóng gói cẩn thận"

Quy tắc bắt buộc:
- MỖI trích dẫn phải bắt đầu bằng `> ` trên DÒNG RIÊNG — KHÔNG gộp nhiều quote trên cùng một dòng
- CHỈ trích dẫn nguyên văn trong dấu ngoặc kép
- BỎ QUA các bình luận chỉ có mỗi icon hoặc dưới 6 ký tự
- KHÔNG thêm nhận xét như "tốt", "xấu", "hài lòng", "thất vọng"
- Giữ nguyên ngôn ngữ gốc kể cả teencode, Vienglish
- Kết thúc bằng dòng: 📊 Tổng hợp: {n} reviews từ {source}

Reviews:
{reviews}
"""

_HISTORY_MARKER = "\n[Câu hỏi hiện tại]\n"
_VIET_RE = re.compile(
    r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]",
    re.IGNORECASE,
)
_EMOJI_ONLY_RE = re.compile(
    r"^[\s\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0000FE00-\U0000FEFF!?.…,]+$"
)
_INLINE_QUOTES_RE = re.compile(r'"([^"]+)"')
_COMMERCE_RE = re.compile(
    r"\b(giá|pin|sạc|bh|bảo hành|shop|mua|bán|xài|dùng|chất|ok|oke|xịn|keng|body|màn|active|trả|vn/a|like new)\b",
    re.IGNORECASE,
)
_FOREIGN_RE = re.compile(
    r"\b(perai|mesmo|tamanho|gimana|bagus|sangat|kenapa|kak|anh|bro)\b",
    re.IGNORECASE,
)
_PRODUCT_STOPWORDS = frozenset({
    "review", "cho", "mình", "biết", "về", "của", "the", "người", "dùng",
    "nói", "gì", "là", "có", "không", "như", "thế", "nào", "bao", "nhiêu",
})


def _product_hint(task: str, fallback: str) -> str:
    question = task.split(_HISTORY_MARKER)[-1].strip() if task else ""
    for pattern in (
        r"về\s+(.+?)(?:\?|$)",
        r"review\s+(.+?)(?:\?|$)",
        r"đánh giá\s+(.+?)(?:\?|$)",
        r"phân tích\s+(.+?)(?:\?|$)",
    ):
        match = re.search(pattern, question, re.IGNORECASE)
        if match:
            hint = match.group(1).strip(" \"'")
            if 3 <= len(hint) <= 80:
                return hint
    for prefix in ("review ", "đánh giá ", "tìm hiểu ", "phân tích "):
        if question.lower().startswith(prefix):
            question = question[len(prefix):].strip()
    if question and len(question) <= 120:
        return question
    return fallback or "sản phẩm"


def _product_tokens(product: str) -> List[str]:
    tokens = re.findall(r"[a-z0-9]{2,}", product.lower())
    return [t for t in tokens if t not in _PRODUCT_STOPWORDS]


def _is_viet_or_english(text: str) -> bool:
    if _VIET_RE.search(text):
        return True
    letters = re.findall(r"[a-zA-Z]", text)
    return len(letters) >= max(4, len(text.strip()) * 0.4)


def _is_noise(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 6:
        return True
    if _EMOJI_ONLY_RE.match(stripped):
        return True
    return False


def filter_reviews(reviews: List[Dict], product: str) -> List[Dict]:
    tokens = _product_tokens(product)
    filtered: List[Dict] = []

    for review in reviews:
        text = (review.get("content") or review.get("comment") or review.get("text") or "").strip()
        if not text or _is_noise(text):
            continue
        if not _is_viet_or_english(text):
            continue
        if _FOREIGN_RE.search(text) and not _VIET_RE.search(text):
            continue

        lower = text.lower()
        matches_product = tokens and any(token in lower for token in tokens)
        matches_topic = bool(_COMMERCE_RE.search(lower))

        if tokens and not matches_product and not matches_topic:
            continue

        filtered.append({**review, "content": text})

    return filtered


def _format_reviews(reviews: List[Dict]) -> str:
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


def _normalize_review_markdown(text: str) -> str:
    lines: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if (
            stripped
            and not stripped.startswith(">")
            and not stripped.startswith("#")
            and not stripped.startswith("📊")
            and '"' in stripped
        ):
            quotes = _INLINE_QUOTES_RE.findall(stripped)
            if len(quotes) >= 2:
                for quote in quotes:
                    lines.append(f'> "{quote}"')
                    lines.append("")
                continue
        lines.append(line)
    return "\n".join(lines)


async def summarize_reviews(
    reviews: List[Dict],
    product: str = "",
    source: str = "",
    task: str = "",
) -> Optional[str]:
    if not reviews:
        return None

    product_hint = _product_hint(task, product)
    relevant = filter_reviews(reviews, product_hint)
    if not relevant:
        relevant = [r for r in reviews if (r.get("content") or "").strip()][:40]

    prompt = REVIEW_SUMMARY_PROMPT.format(
        n=len(relevant),
        product=product_hint,
        source=source,
        reviews=_format_reviews(relevant),
    )

    response = await create_response(
        model=_cfg.OPENAI_MODEL,
        instructions=_SYSTEM,
        input=prompt,
        max_output_tokens=_cfg.OPENAI_MAX_TOKENS,
    )
    raw = extract_response_text(response)
    if not raw:
        return None
    normalized = _normalize_review_markdown(raw)
    return re.sub(
        r"📊 Tổng hợp:.*",
        f"📊 Tổng hợp: {len(relevant)} reviews từ {source}",
        normalized,
        count=1,
    )
