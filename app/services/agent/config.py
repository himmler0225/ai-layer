import app.config.settings as _cfg


def tool_model() -> str:
    """Model gọi tool (có thể khác model tổng hợp)."""
    return _cfg.OPENAI_TOOL_MODEL or _cfg.OPENAI_MODEL


def synth_model() -> str:
    """Model viết câu trả lời cuối."""
    return _cfg.OPENAI_MODEL


def dual_mode() -> bool:
    """Bật khi TOOL_MODEL ≠ MODEL — tách bước crawl và synthesis."""
    return bool(_cfg.OPENAI_TOOL_MODEL) and _cfg.OPENAI_TOOL_MODEL != _cfg.OPENAI_MODEL


def tool_max_tokens() -> int:
    """Giới hạn token cho bước gọi tool."""
    return _cfg.OPENAI_TOOL_MAX_TOKENS if dual_mode() else _cfg.OPENAI_MAX_TOKENS


def synth_max_tokens() -> int:
    """Giới hạn token cho bước tổng hợp câu trả lời."""
    return _cfg.OPENAI_MAX_TOKENS


def max_result_chars() -> int:
    """Giới hạn độ dài tool result đưa lại model."""
    return _cfg.AGENT_MAX_RESULT_CHARS


def max_comments() -> int:
    """Số comment tối đa giữ lại mỗi lần gọi tool."""
    return _cfg.AGENT_MAX_COMMENTS


def max_comment_len() -> int:
    """Độ dài tối đa mỗi comment trong result."""
    return _cfg.AGENT_MAX_COMMENT_LEN


def max_list_items() -> int:
    """Số phần tử tối đa mỗi list trong result."""
    return _cfg.AGENT_MAX_LIST_ITEMS