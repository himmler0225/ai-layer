import app.config.settings as settings
from app.ai.router import TASK_AGENT_SYNTH, TASK_AGENT_TOOL, max_tokens_for_task, resolve


def tool_model() -> str:
    """Tool model.

    Returns:
        (str) Kết quả trả về."""
    _, model = resolve(TASK_AGENT_TOOL)
    return model


def synth_model() -> str:
    """Synth model.

    Returns:
        (str) Kết quả trả về."""
    _, model = resolve(TASK_AGENT_SYNTH)
    return model


def dual_mode() -> bool:
    """True khi tool round và synthesis dùng provider hoặc model khác nhau."""
    p_tool, m_tool = resolve(TASK_AGENT_TOOL)
    p_synth, m_synth = resolve(TASK_AGENT_SYNTH)
    if p_tool != p_synth:
        return True
    return m_tool != m_synth


def tool_max_tokens() -> int:
    """Tool max tokens.

    Returns:
        (int) Kết quả trả về."""
    return max_tokens_for_task(TASK_AGENT_TOOL)


def synth_max_tokens() -> int:
    """Synth max tokens.

    Returns:
        (int) Kết quả trả về."""
    return max_tokens_for_task(TASK_AGENT_SYNTH)


def include_review_summary() -> bool:
    """Có gọi review_summarizer sau agent không (Supabase AI_AGENT.include_review_summary)."""
    return bool(getattr(settings, "AGENT_INCLUDE_REVIEW_SUMMARY", True))


def max_result_chars() -> int:
    """Max result chars.

    Returns:
        (int) Kết quả trả về."""
    return settings.AGENT_MAX_RESULT_CHARS


def max_comments() -> int:
    """Max comments.

    Returns:
        (int) Kết quả trả về."""
    return settings.AGENT_MAX_COMMENTS


def max_comment_len() -> int:
    """Max comment len.

    Returns:
        (int) Kết quả trả về."""
    return settings.AGENT_MAX_COMMENT_LEN


def max_list_items() -> int:
    """Max list items.

    Returns:
        (int) Kết quả trả về."""
    return settings.AGENT_MAX_LIST_ITEMS
