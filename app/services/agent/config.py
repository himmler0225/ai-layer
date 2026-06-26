import app.config.settings as _cfg
from app.ai.router import (
    TASK_AGENT_SYNTH,
    TASK_AGENT_TOOL,
    max_tokens_for_task,
    resolve,
)


def tool_model() -> str:
    """Model gọi tool (DeepSeek khi dual-mode)."""
    _, model = resolve(TASK_AGENT_TOOL)
    return model


def synth_model() -> str:
    """Model viết câu trả lời cuối (OpenAI)."""
    _, model = resolve(TASK_AGENT_SYNTH)
    return model


def dual_mode() -> bool:
    """Bật khi tool provider ≠ synth provider."""
    p_tool, _ = resolve(TASK_AGENT_TOOL)
    p_synth, _ = resolve(TASK_AGENT_SYNTH)
    return p_tool != p_synth


def tool_max_tokens() -> int:
    """Giới hạn token cho bước gọi tool."""
    return max_tokens_for_task(TASK_AGENT_TOOL)


def synth_max_tokens() -> int:
    """Giới hạn token cho bước tổng hợp câu trả lời."""
    return max_tokens_for_task(TASK_AGENT_SYNTH)


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
