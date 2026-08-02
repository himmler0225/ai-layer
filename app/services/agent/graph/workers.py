import json
import re
import uuid
from typing import Any

from app.ai.router import TASK_AGENT_TOOL
from app.ai.types import FunctionCallItem
from app.services.agent import config
from app.services.agent.core.context import bootstrap_agent, begin_tool_round, complete_tool_round, is_max_tokens_incomplete
from app.services.agent.core.engine import resolve_empty_tool_round, tool_round_action
from app.services.agent.guards.fallback import catalog_fallback_call
from app.utils.llm_responses import create_response, extract_response_text, status_error
from app.config.logger import Logger

logger = Logger.get(__name__)

_SCRATCHPAD_ONLY = re.compile(r"intent\s*=\s*[\"']?(catalog|review|media|h[oỗ]n\s*h[oợ]p)", re.IGNORECASE)
_MOVIE_NAME_RE = re.compile(r'last_movie_name["\']?\s*[:=]\s*["\']?([^,"\'}]+)', re.IGNORECASE)


def _is_scratchpad_only(text: str) -> bool:
    return bool(_SCRATCHPAD_ONLY.search(text[:200]))


def _extract_movie_name(text: str) -> str | None:
    m = _MOVIE_NAME_RE.search(text[:400])
    if not m:
        return None
    name = m.group(1).strip()
    return name or None


def _build_search_fallback(*, tools: list[dict], search_tool: str | None, search_arg: str | None, movie_name: str | None) -> FunctionCallItem | None:
    if not search_tool or not search_arg or not movie_name:
        return None
    names = {t.get("name", "") for t in tools if t.get("name")}
    if search_tool not in names:
        return None
    return FunctionCallItem(
        call_id=f"fallback_{uuid.uuid4().hex[:12]}",
        name=search_tool,
        arguments=json.dumps({search_arg: movie_name}),
    )


async def run_worker_loop(
    *,
    domain: str,
    task: str,
    tools: list[dict],
    system: str,
    max_iter: int,
    search_tool: str | None = None,
    search_arg: str | None = None,
) -> list[dict]:
    ctx = await bootstrap_agent(task, tools, system, max_iter)
    scratchpad_movie_name: str | None = None

    for iteration in range(1, ctx["max_iter"] + 1):
        tool_choice: Any = "required" if not ctx["tool_call_log"] else "auto"
        call_items: list = []

        for attempt in range(3):
            final = await create_response(
                task=TASK_AGENT_TOOL,
                model=config.tool_model(),
                max_output_tokens=config.tool_max_tokens(),
                instructions=ctx["system"],
                tools=ctx["tools"],
                tool_choice=tool_choice,
                input=ctx["input_items"],
            )
            err = status_error(final)
            if err:
                logger.warning("[worker:%s] llm error: %s", domain, err)
                return ctx["tool_call_log"]

            if is_max_tokens_incomplete(final):
                logger.warning("[worker:%s] max_tokens incomplete iter=%d", domain, iteration)
                return ctx["tool_call_log"]

            call_items = await begin_tool_round(ctx, final.output)
            if call_items:
                break

            collected_text = extract_response_text(final)
            logger.debug(
                "[worker:%s] iter=%d attempt=%d tool_choice=%s call_items=0 text=%r",
                domain, iteration, attempt, tool_choice, collected_text[:200],
            )
            scratchpad_only = _is_scratchpad_only(collected_text)
            if scratchpad_only and scratchpad_movie_name is None:
                scratchpad_movie_name = _extract_movie_name(collected_text)

            next_choice = resolve_empty_tool_round(
                ctx, iteration=iteration, attempt=attempt,
                call_items=call_items,
                collected_text="" if scratchpad_only else collected_text,
                tool_choice=tool_choice,
            )
            if next_choice is None:
                break
            tool_choice = next_choice

        used_fallback = False
        if not call_items:
            fallback = catalog_fallback_call(ctx["task"], ctx["tools"])
            if fallback:
                call_items = await begin_tool_round(ctx, [fallback])
                used_fallback = True

        if not call_items and scratchpad_movie_name:
            fallback = _build_search_fallback(
                tools=ctx["tools"],
                search_tool=search_tool, search_arg=search_arg,
                movie_name=scratchpad_movie_name,
            )
            if fallback:
                logger.warning(
                    "[worker:%s] scratchpad fallback search tool=%s movie=%r",
                    domain, search_tool, scratchpad_movie_name,
                )
                call_items = await begin_tool_round(ctx, [fallback])
                used_fallback = True

        if not call_items:
            break

        await complete_tool_round(ctx, list(call_items), iteration)

        if used_fallback or tool_round_action(ctx, iteration) == "force_synthesis":
            break

    for entry in ctx["tool_call_log"]:
        entry["worker"] = domain
    return ctx["tool_call_log"]
