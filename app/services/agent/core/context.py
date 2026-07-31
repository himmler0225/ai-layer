import uuid
from typing import Any
from app.config.logger import Logger
from app.exceptions import AiLayerConfigError
from app.services.agent import config
from app.rag.movie_hint import enrich_short_followup_task
from app.services.agent.tooling import execute_parallel, extract_function_calls, prepare_tools_for_task
from app.services.agent.guards import apply_tool_budget, extract_video_items
from app.services.agent.synthesis import finish, run_synthesis
from app.utils.llm_responses import extract_response_text, is_incomplete_for, output_items_to_input

logger = Logger.get(__name__)


def new_context(*, task: str, tools: list[dict], system: str, max_iter: int) -> dict[str, Any]:
    """New context.

    Args:
        task: (str) Tham số `task`.
        tools: (List[Dict]) Tham số `tools`.
        system: (str) Tham số `system`.
        max_iter: (int) Tham số `max_iter`.

    Returns:
        (Dict[str, Any]) Kết quả trả về."""
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
    """Khởi tạo agent (async).

    Args:
        task: (str) Tham số `task`.
        tools: (List[Dict]) Tham số `tools`.
        system: (Optional[str]) Tham số `system`.
        max_iter: (int) Tham số `max_iter`.

    Returns:
        (Dict[str, Any]) Kết quả trả về."""
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
        "[agent] bootstrap tools=%d movie=%d",
        len(prepared),
        sum(1 for t in prepared if t.get("name", "").startswith("movie_")),
    )
    return new_context(task=task, tools=prepared, system=resolved_system, max_iter=max_iter)


def extract_calls(output: Any) -> list[Any]:
    """Trích xuất calls.

    Args:
        output: (Any) Tham số `output`.

    Returns:
        (List[Any]) Kết quả trả về."""
    return extract_function_calls(output)


def is_max_tokens_incomplete(response: Any) -> bool:
    """Is max tokens incomplete.

    Args:
        response: (Any) Tham số `response`.

    Returns:
        (bool) Kết quả trả về."""
    return is_incomplete_for("max_output_tokens", response)


async def begin_tool_round(ctx: dict[str, Any], output: Any) -> list[Any]:
    """Begin tool round (async).

    Args:
        ctx: (Dict[str, Any]) Tham số `ctx`.
        output: (Any) Tham số `output`.

    Returns:
        (List[Any]) Kết quả trả về."""
    call_items = extract_calls(output)
    if not call_items:
        return []
    ctx["input_items"].extend(output_items_to_input(output))
    return call_items


async def complete_tool_round(ctx: dict[str, Any], output: Any, iteration: int) -> None:
    """Hoàn tất tool round (async).

    Args:
        ctx: (Dict[str, Any]) Tham số `ctx`.
        output: (Any) Tham số `output`.
        iteration: (int) Tham số `iteration`.

    Returns:
        (None) Kết quả trả về."""
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


async def resolve_final_text(ctx: dict[str, Any], response: Any) -> str:
    """Giải quyết final text (async).

    Args:
        ctx: (Dict[str, Any]) Tham số `ctx`.
        response: (Any) Tham số `response`.

    Returns:
        (str) Kết quả trả về."""
    if config.dual_mode() and ctx["tool_call_log"]:
        return await run_synthesis(
            system=ctx["system"],
            task=ctx["task"],
            tool_call_log=ctx["tool_call_log"],
        )
    return extract_response_text(response)


async def finish_agent(
    ctx: dict[str, Any], *, iteration: int, final_text: str, include_summary: bool | None = None
) -> dict[str, Any]:
    """Hoàn tất agent (async).

    Args:
        ctx: (Dict[str, Any]) Tham số `ctx`.
        iteration: (int) Tham số `iteration`.
        final_text: (str) Tham số `final_text`.
        include_summary: (bool | None) Override AGENT_INCLUDE_REVIEW_SUMMARY.

    Returns:
        (Dict[str, Any]) Kết quả trả về."""
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
    """Video preview.

    Args:
        tool_call_log: (List[Dict]) Tham số `tool_call_log`.

    Returns:
        (List[Dict]) Kết quả trả về."""
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
