import app.config.settings as settings
from app.ai.router import TASK_AGENT_SYNTH, TASK_AGENT_TOOL, max_tokens_for_task, resolve

def tool_model() -> str:
    _, model = resolve(TASK_AGENT_TOOL)
    return model

def synth_model() -> str:
    _, model = resolve(TASK_AGENT_SYNTH)
    return model

def dual_mode() -> bool:
    p_tool, _ = resolve(TASK_AGENT_TOOL)
    p_synth, _ = resolve(TASK_AGENT_SYNTH)
    return p_tool != p_synth

def tool_max_tokens() -> int:
    return max_tokens_for_task(TASK_AGENT_TOOL)

def synth_max_tokens() -> int:
    return max_tokens_for_task(TASK_AGENT_SYNTH)

def max_result_chars() -> int:
    return settings.AGENT_MAX_RESULT_CHARS

def max_comments() -> int:
    return settings.AGENT_MAX_COMMENTS

def max_comment_len() -> int:
    return settings.AGENT_MAX_COMMENT_LEN

def max_list_items() -> int:
    return settings.AGENT_MAX_LIST_ITEMS
