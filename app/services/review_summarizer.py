"""
Quote-based review clustering via Claude.

Instead of classifying positive/negative (which loses context),
Claude groups comments by TOPIC and quotes them verbatim.
Users interpret meaning themselves — no model bias.
"""
import anthropic
from typing import Dict, List, Optional

from app.config.settings import ANTHROPIC_API_KEY, CLAUDE_MODEL

_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

_SYSTEM = (
    "Bạn là công cụ tổng hợp reviews thương mại điện tử. "
    "Nhiệm vụ duy nhất: cluster theo chủ đề + trích dẫn nguyên văn. "
    "TUYỆT ĐỐI không thêm nhận xét cá nhân, không dùng từ 'tốt'/'xấu'/'tệ'."
)

REVIEW_SUMMARY_PROMPT = """\
Bạn nhận được {n} comments/reviews về sản phẩm "{product}".

Nhiệm vụ:
1. Nhóm các comments theo CHỦ ĐỀ (chất lượng, giao hàng, giá cả, kích cỡ, dịch vụ, độ bền...)
2. Với mỗi chủ đề, trích dẫn NGUYÊN VĂN 2-3 comments đại diện
3. Ghi rõ số lượng comments đề cập đến chủ đề đó
4. Nếu được, trích xuất luôn tên và avatar người dùng kèm thời gian để tăng mức độ tin cậy

Format output (giữ đúng format, thêm emoji phù hợp):

### 📦 Chất lượng sản phẩm (23 lượt đề cập)
> "2 tuần là xanh màn"
> "dùng 3 tháng vẫn tốt, không có vấn đề gì"
> "hàng y hình, chất lượng như mô tả"

### 🚚 Giao hàng (15 lượt đề cập)
> "ship 2 ngày, đóng gói cẩn thận"
> "giao hơi chậm nhưng hàng nguyên vẹn"

### 💰 Giá cả (8 lượt đề cập)
> "giá ok so với chất lượng"
> "hơi đắt so với chỗ khác"

Quy tắc bắt buộc:
- CHỈ trích dẫn nguyên văn trong dấu ngoặc kép
- KHÔNG thêm nhận xét như "tốt", "xấu", "hài lòng", "thất vọng"
- Với những câu có tổn tại những từ như "vc", "vl" thì không xếp nó vào tích cực hay tiêu cực
- Giữ nguyên ngôn ngữ gốc kể cả teencode, Vienglish
- Không bỏ sót comments quan trọng dù khó phân loại
- Kết thúc bằng dòng: 📊 Tổng hợp: {n} reviews từ {source}

Reviews:
{reviews}
"""


def _format_reviews(reviews: List[Dict]) -> str:
    lines = []
    for i, r in enumerate(reviews[:150], 1):
        text    = r.get("content") or r.get("comment") or r.get("text") or ""
        rating  = r.get("rating") or r.get("stars") or "?"
        if text:
            lines.append(f"{i}. [{rating}★] {text[:300]}")
    return "\n".join(lines)


async def summarize_reviews(
    reviews: List[Dict],
    product: str = "",
    source: str = "",
) -> Optional[str]:
    if not reviews:
        return None

    prompt = REVIEW_SUMMARY_PROMPT.format(
        n=len(reviews),
        product=product,
        source=source,
        reviews=_format_reviews(reviews),
    )

    msg = await _client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
    )

    return msg.content[0].text
