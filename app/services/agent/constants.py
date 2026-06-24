import re

# Phân tách lịch sử chat và câu hỏi hiện tại trong task
HISTORY_MARKER = "\n[Câu hỏi hiện tại]\n"

_TIKTOK = re.compile(r"\btiktok\b", re.IGNORECASE)
_YOUTUBE = re.compile(r"\byoutube\b", re.IGNORECASE)
