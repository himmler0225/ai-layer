from typing import Dict, List, Optional

import app.config.settings as _cfg
from app.utils.openai_responses import create_response, extract_response_text

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
- BỎ QUA các bình luận chỉ có mỗi icon
- KHÔNG thêm nhận xét như "tốt", "xấu", "hài lòng", "thất vọng"
- Với những câu có tổn tại những từ như "vc", "vl" thì không xếp nó vào tích cực hay tiêu cực
- Giữ nguyên ngôn ngữ gốc kể cả teencode, Vienglish
- Không bỏ sót comments quan trọng dù khó phân loại
- Nếu một số ít comments dùng ngôn ngữ KHÁC HẲN với phần lớn comments còn lại (ví dụ lẫn tiếng Indonesia, Malay, Thái... trong tập chủ yếu tiếng Việt/Anh) → BỎ QUA HOÀN TOÀN các comment đó, không trích dẫn, không tính vào số lượng đề cập của bất kỳ chủ đề nào
- Mỗi dòng input có thể có tiền tố "[X★]" nếu nguồn gốc là review có rating sao thật — đây KHÔNG phải một phần nội dung comment, chỉ dùng nó để biết mức độ hài lòng nếu cần, KHÔNG bao giờ chép tiền tố "[X★]" này vào câu trích dẫn
- Kết thúc bằng dòng: 📊 Tổng hợp: {n} reviews từ {source}

Reviews:
{reviews}
"""


def _format_reviews(reviews: List[Dict]) -> str:
    lines = []
    for i, review in enumerate(reviews[:150], 1):
        text = review.get("content") or review.get("comment") or review.get("text") or ""
        rating = review.get("rating") or review.get("stars")
        if not text:
            continue
        prefix = f"[{rating}★] " if rating else ""
        lines.append(f"{i}. {prefix}{text[:300]}")
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

    response = await create_response(
        model=_cfg.OPENAI_MODEL,
        instructions=_SYSTEM,
        input=prompt,
        max_output_tokens=_cfg.OPENAI_MAX_TOKENS,
    )
    return extract_response_text(response)
