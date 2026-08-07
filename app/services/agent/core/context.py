import uuid
from typing import Any
from app.config.logger import Logger, log_event
from app.exceptions import AiLayerConfigError
from app.services.agent import config
from app.rag.movie_hint import enrich_short_followup_task
from app.services.agent.tooling import execute_parallel, extract_function_calls, prepare_tools_for_task
from app.services.agent.guards import apply_tool_budget, extract_video_items
from app.services.agent.synthesis import finish
from app.utils.llm_responses import is_incomplete_for, output_items_to_input

logger = Logger.get(__name__)


def new_context(*, task: str, tools: list[dict], system: str, max_iter: int) -> dict[str, Any]:
    """Build a fresh agent run context (session id, conversation state, tool call log).

    Args:
        task: (str) The user task/question, used to seed the first input item.
        tools: (List[Dict]) Tool definitions available to the agent for this run.
        system: (str) System prompt to use for the run.
        max_iter: (int) Maximum number of tool-calling iterations allowed.

    Returns:
        (Dict[str, Any]) New context dict with session_id, task, system, tools,
        max_iter, input_items (seeded with the user task) and an empty tool_call_log."""
    return {
        "session_id": str(uuid.uuid4()),
        "task": task,
        "system": system,
        "tools": tools,
        "max_iter": max_iter,
        "input_items": [{"role": "user", "content": task}],
        "tool_call_log": [],
    }


async def bootstrap_agent(task: str, tools: list[dict], system: str | None, max_iter: int) -> dict[str, Any]:
    """Resolve the system prompt, enrich the task, prepare tools, and build the run context.

    Falls back to the configured AGENT_SYSTEM prompt when `system` is not
    provided, enriches short follow-up tasks with movie context, and resolves
    the given tool definitions against the task before creating the context.

    Args:
        task: (str) The user task/question.
        tools: (List[Dict]) Raw tool definitions to prepare for this task.
        system: (Optional[str]) System prompt override; falls back to AGENT_SYSTEM.
        max_iter: (int) Maximum number of tool-calling iterations allowed.

    Returns:
        (Dict[str, Any]) New agent context built via `new_context`, with the
        enriched task and prepared tools.

    Raises:
        AiLayerConfigError: If no system prompt is configured or provided."""
    import app.services.prompts as _prompts

    resolved_system = system or _prompts.AGENT_SYSTEM
    if not (resolved_system or "").strip():
        raise AiLayerConfigError(
            "AGENT_SYSTEM chưa cấu hình — thêm key trên Supabase config",
            message_key="errors.config_agent_system",
        )
    task = enrich_short_followup_task(task)
    prepared = await prepare_tools_for_task(tools, task)
    logger.info(
        log_event(
            "agent",
            "bootstrap complete",
            tools=len(prepared),
            movie_tools=sum(1 for t in prepared if t.get("name", "").startswith("movie_")),
        )
    )
    return new_context(task=task, tools=prepared, system=resolved_system, max_iter=max_iter)


def extract_calls(output: Any) -> list[Any]:
    """Extract function/tool call items from a model response.

    Args:
        output: (Any) Raw LLM response output.

    Returns:
        (List[Any]) Function call items found in the response, if any."""
    return extract_function_calls(output)


def is_max_tokens_incomplete(response: Any) -> bool:
    """Check whether a response was cut off because it hit the max output token limit.

    Args:
        response: (Any) Raw LLM response to inspect.

    Returns:
        (bool) True if the response is incomplete due to max_output_tokens."""
    return is_incomplete_for("max_output_tokens", response)


async def begin_tool_round(ctx: dict[str, Any], output: Any) -> list[Any]:
    """Extract tool calls from a model response and append the response to the context's input items.

    Args:
        ctx: (Dict[str, Any]) Agent run context, mutated in place (input_items extended).
        output: (Any) Raw LLM response output to inspect for tool calls.

    Returns:
        (List[Any]) The extracted function call items, or an empty list if
        there were none (in which case the context is left unmodified)."""
    call_items = extract_calls(output)
    if not call_items:
        return []
    ctx["input_items"].extend(output_items_to_input(output))
    return call_items


async def complete_tool_round(ctx: dict[str, Any], output: Any, iteration: int) -> None:
    """Execute the pending tool calls in parallel and fold the results back into the context.

    Runs all tool calls found in `output` concurrently, appends their outputs to
    the context's input items and tool_call_log, then enforces the tool budget
    (which may trim the log or raise if the budget is exceeded).

    Args:
        ctx: (Dict[str, Any]) Agent run context, mutated in place.
        output: (Any) Raw LLM response output containing the tool calls to run.
        iteration: (int) Current tool-round iteration number, used for logging/limits.

    Returns:
        (None) The context is updated in place."""
    outputs, entries = await execute_parallel(
        output,
        ctx["session_id"],
        ctx["task"],
        iteration,
        tool_call_log=ctx["tool_call_log"],
    )
    ctx["tool_call_log"].extend(entries)
    ctx["input_items"].extend(outputs)
    apply_tool_budget(ctx)


async def finish_agent(
    ctx: dict[str, Any], *, iteration: int, final_text: str, include_summary: bool | None = None
) -> dict[str, Any]:
    """Finalize the agent run, optionally adding a review summary, and build the response payload.

    Args:
        ctx: (Dict[str, Any]) Agent run context (session_id, task, tool_call_log).
        iteration: (int) Final iteration count reached.
        final_text: (str) The agent's final synthesized answer text.
        include_summary: (bool | None) Override AGENT_INCLUDE_REVIEW_SUMMARY.

    Returns:
        (Dict[str, Any]) Finalized result payload produced by `finish`."""
    use_summary = config.include_review_summary() if include_summary is None else include_summary
    return await finish(
        session_id=ctx["session_id"],
        task=ctx["task"],
        iteration=iteration,
        tool_call_log=ctx["tool_call_log"],
        final_text=final_text,
        include_summary=use_summary,
    )


def video_preview(tool_call_log: list[dict]) -> list[dict]:
    """Collect up to 10 unique video items found in a tool call log, for preview purposes.

    Args:
        tool_call_log: (List[Dict]) Tool call log entries, each possibly holding a "result".

    Returns:
        (List[Dict]) Up to 10 deduplicated video items (by video_id), in the
        order they were encountered."""
    seen: set[str] = set()
    preview: list[dict] = []
    for entry in tool_call_log:
        for video in extract_video_items(entry.get("result")):
            vid = video.get("video_id") if isinstance(video, dict) else None
            if vid and vid not in seen:
                seen.add(vid)
                preview.append(video)
                if len(preview) >= 10:
                    return preview
    return preview
