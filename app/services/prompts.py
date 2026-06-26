"""Prompt LLM — AGENT_* và REVIEW_* nằm trên Supabase `config`, load qua remote.py."""

AGENT_SYSTEM = ""
AGENT_SYNTH_SYSTEM = ""
REVIEW_SUMMARY_SYSTEM = ""
REVIEW_SUMMARY_PROMPT = ""

# RAG summarize (chưa đưa lên config)
ASPECT_GROUP_SYSTEM = (
    "Bạn phân loại review sản phẩm theo aspect. "
    "Trả JSON hợp lệ với key groups — mỗi nhóm có aspect, review_ids, content, "
    "positive_percent, negative_percent. Không markdown."
)

ASPECT_GROUP_PROMPT = """\
Sản phẩm: {product}
Aspect hợp lệ: {aspects}

Nhóm các review sau theo aspect. Gộp nội dung liên quan vào content (tiếng Việt).
Chỉ dùng review_ids có trong danh sách (trường id=...).
Bỏ qua spam, comment không liên quan sản phẩm.

Format JSON:
{{"groups": [{{"aspect": "battery", "review_ids": ["yt:..."], "content": "...", "positive_percent": 80, "negative_percent": 20}}]}}

Reviews:
{reviews}
"""

ASPECT_SUMMARY_SYSTEM = (
    "Bạn tóm tắt khách quan review theo một aspect. "
    "JSON: summary, pros (list), cons (list), positive_percent (0-100). Không markdown."
)

ASPECT_SUMMARY_PROMPT = """\
Sản phẩm: {product}
Aspect: {aspect}

Nội dung review đã nhóm:
{content}

Tóm tắt ngắn gọn tiếng Việt, khách quan, không tư vấn mua/bán.
"""
