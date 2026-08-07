import app.config.settings as settings
from app.ai.router import TASK_AGENT_SYNTH, TASK_AGENT_TOOL, max_tokens_for_task, resolve


def tool_model() -> str:
    """Resolve the model id to use for the agent's tool-calling round.

    Returns:
        (str) Model identifier resolved for the TASK_AGENT_TOOL task."""
    _, model = resolve(TASK_AGENT_TOOL)
    return model


def synth_model() -> str:
    """Resolve the model id to use for the agent's synthesis (final answer) round.

    Returns:
        (str) Model identifier resolved for the TASK_AGENT_SYNTH task."""
    _, model = resolve(TASK_AGENT_SYNTH)
    return model


def dual_mode() -> bool:
    """True when the tool round and the synthesis round use a different provider or model."""
    p_tool, m_tool = resolve(TASK_AGENT_TOOL)
    p_synth, m_synth = resolve(TASK_AGENT_SYNTH)
    if p_tool != p_synth:
        return True
    return m_tool != m_synth


def tool_max_tokens() -> int:
    """Max output tokens allowed for the tool-calling round.

    Returns:
        (int) Max token budget configured for TASK_AGENT_TOOL."""
    return max_tokens_for_task(TASK_AGENT_TOOL)


def synth_max_tokens() -> int:
    """Max output tokens allowed for the synthesis round.

    Returns:
        (int) Max token budget configured for TASK_AGENT_SYNTH."""
    return max_tokens_for_task(TASK_AGENT_SYNTH)


def include_review_summary() -> bool:
    """Whether review_summarizer should run after the agent (Supabase AI_AGENT.include_review_summary)."""
    return bool(getattr(settings, "AGENT_INCLUDE_REVIEW_SUMMARY", True))


def max_result_chars() -> int:
    """Max character length allowed for a single tool result before truncation.

    Returns:
        (int) Configured AGENT_MAX_RESULT_CHARS value."""
    return settings.AGENT_MAX_RESULT_CHARS


def max_comments() -> int:
    """Max number of comments kept when summarizing/serializing a review-style result.

    Returns:
        (int) Configured AGENT_MAX_COMMENTS value."""
    return settings.AGENT_MAX_COMMENTS


def max_comment_len() -> int:
    """Max character length allowed per individual comment.

    Returns:
        (int) Configured AGENT_MAX_COMMENT_LEN value."""
    return settings.AGENT_MAX_COMMENT_LEN


def max_list_items() -> int:
    """Max number of items kept when serializing a list-style tool result.

    Returns:
        (int) Configured AGENT_MAX_LIST_ITEMS value."""
    return settings.AGENT_MAX_LIST_ITEMS
