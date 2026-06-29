import re
HISTORY_MARKER = '\n[Câu hỏi hiện tại]\n'
_TIKTOK = re.compile('\\btiktok\\b', re.IGNORECASE)
_YOUTUBE = re.compile('\\byoutube\\b', re.IGNORECASE)
