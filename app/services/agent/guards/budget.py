import json
from typing import Any

from app.config.logger import Logger, log_event

logger = Logger.get(__name__)

# Same tool + identical input (applies to non-search tools).
_MAX_SAME_SIGNATURE = 2
# Same tool name (different keyword) — applies to non-search tools.
_MAX_SAME_TOOL_NAME = 2
# Total number of tool calls (of any kind) before forcing synthesis (once there is data).
_MAX_TOOL_ROUNDS_SOFT = 6
# Extra rounds allowed when there are no comments/transcript/RAG yet.
_MAX_TOOL_ROUNDS_NO_EVIDENCE = 10
# Model keeps calling search even after being blocked by the budget.
_MAX_STUBBORN_SEARCH = 4

_SEARCH_TOOLS: set[str] = frozenset({"youtube_search", "tiktok_search"})
# Each platform may only be searched once; subsequent calls remove it from the tool menu.
_MAX_SEARCH_PER_PLATFORM = 1

_EVIDENCE_TOOLS: set[str] = frozenset(
    {
        "youtube_get_comments_batch",
        "youtube_get_comments",
        "youtube_get_transcript",
        "youtube_get_transcript_batch",
        "tiktok_comments",
        "search_movie_summary",
        "search_aspect_evidence",
        "get_raw_reviews",
    }
)


def tool_signature(name: str, inputs: dict[str, Any]) -> str:
    """Build a stable signature identifying a tool call by name and its exact input.

    Used to detect repeated identical tool calls (same tool, same arguments).

    Args:
        name: (str) Tool name.
        inputs: (dict[str, Any]) Tool call input arguments.

    Returns:
        (str) A "name:json_payload" string, with `inputs` serialized as
        sorted-key JSON (or "{}" if it isn't JSON-serializable)."""
    try:
        payload = json.dumps(inputs or {}, sort_keys=True, ensure_ascii=False)
    except TypeError:
        payload = "{}"
    return f"{name}:{payload}"


def count_tool_name(log: list[dict[str, Any]], name: str) -> int:
    """Count how many entries in a tool call log used a given tool name.

    Args:
        log: (list[dict[str, Any]]) Tool call log entries.
        name: (str) Tool name to count occurrences of.

    Returns:
        (int) Number of log entries whose "tool" matches `name`."""
    return sum(1 for entry in log if entry.get("tool") == name)


def is_budget_block(entry: dict[str, Any]) -> bool:
    """Check whether a tool call log entry represents a call blocked by the search budget.

    Args:
        entry: (dict[str, Any]) A single tool call log entry.

    Returns:
        (bool) True if the entry's result carries the "search_budget_exhausted" error."""
    result = entry.get("result") or {}
    return result.get("error") == "search_budget_exhausted"


def _result_payload(result: Any) -> dict[str, Any]:
    """(Internal) Unwrap a tool result to the dict actually holding its payload fields.

    Args:
        result: (Any) Raw tool call result, possibly wrapping data under a "data" key.

    Returns:
        (dict[str, Any]) The nested "data" dict if present, otherwise `result`
        itself (or an empty dict if `result` is not a dict)."""
    if not isinstance(result, dict):
        return {}
    data = result.get("data")
    if isinstance(data, dict):
        return data
    return result


def extract_video_items(result: Any) -> list[dict[str, Any]]:
    """Extract the list of video/item dicts from a tool result's payload.

    Args:
        result: (Any) Raw tool call result to search for a video/item list.

    Returns:
        (list[dict[str, Any]]) Items found under the first present "results",
        "videos", or "items" key that holds a list; empty list otherwise."""
    payload = _result_payload(result)
    for key in ("results", "videos", "items"):
        items = payload.get(key)
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


def video_ids_from_log(log: list[dict[str, Any]], *, tool_name: str = "youtube_search") -> list[str]:
    """Collect unique video ids returned by a given search tool across a tool call log.

    Args:
        log: (list[dict[str, Any]]) Tool call log entries to scan.
        tool_name: (str, default 'youtube_search') Tool name whose results to pull video ids from.

    Returns:
        (list[str]) Up to 8 deduplicated video ids (from "video_id" or "id"),
        skipping entries that are budget-blocked or from a different tool."""
    ids: list[str] = []
    for entry in log:
        if entry.get("tool") != tool_name or is_budget_block(entry):
            continue
        for video in extract_video_items(entry.get("result")):
            vid = video.get("video_id") or video.get("id")
            if vid and str(vid) not in ids:
                ids.append(str(vid))
    return ids[:8]


def has_evidence_data(log: list[dict[str, Any]]) -> bool:
    """Check whether the tool call log already contains real evidence (comments, transcripts, RAG hits, or search results).

    Args:
        log: (list[dict[str, Any]]) Tool call log to inspect.

    Returns:
        (bool) True if any non-error, non-budget-blocked entry from an
        evidence tool has comments/transcripts/hits, or a search tool
        returned video items."""
    for entry in log:
        if is_budget_block(entry):
            continue
        name = str(entry.get("tool") or "")
        result = entry.get("result") or {}
        if result.get("error"):
            continue
        if name in _EVIDENCE_TOOLS:
            if result.get("comments") or result.get("transcripts") or result.get("hits"):
                return True
            payload = _result_payload(result)
            if payload.get("comments") or payload.get("transcripts") or payload.get("hits"):
                return True
        if name in _SEARCH_TOOLS and extract_video_items(result):
            return True
    return False


def count_last_signature(log: list[dict[str, Any]]) -> int:
    """Count how many times the most recent tool call's exact signature has appeared in the log.

    Args:
        log: (list[dict[str, Any]]) Tool call log to inspect.

    Returns:
        (int) Number of (non-budget-blocked) entries sharing the last entry's
        tool_signature; 0 if the log is empty."""
    if not log:
        return 0
    last = log[-1]
    sig = tool_signature(str(last.get("tool") or ""), last.get("inputs") or {})
    return sum(
        1
        for entry in log
        if not is_budget_block(entry) and tool_signature(str(entry.get("tool") or ""), entry.get("inputs") or {}) == sig
    )


def count_last_tool_name(log: list[dict[str, Any]]) -> int:
    """Count how many times the most recent tool call's tool name has appeared in the log.

    Args:
        log: (list[dict[str, Any]]) Tool call log to inspect.

    Returns:
        (int) Number of entries using the same tool name as the last entry;
        0 if the log is empty."""
    if not log:
        return 0
    name = str(log[-1].get("tool") or "")
    return count_tool_name(log, name)


def apply_tool_budget(ctx: dict[str, Any]) -> None:
    """After each tool round, remove search tools that have hit their budget so the model switches to comments/RAG."""
    log: list[dict[str, Any]] = ctx.get("tool_call_log") or []
    tools: list[dict[str, Any]] = ctx.get("tools") or []
    remove: set[str] = set()
    for name in _SEARCH_TOOLS:
        if count_tool_name(log, name) >= _MAX_SEARCH_PER_PLATFORM:
            remove.add(name)
    if not remove:
        return
    filtered = [t for t in tools if t.get("name") not in remove]
    if len(filtered) < len(tools):
        logger.info(
            log_event("agent", "tool budget trimmed", removed=sorted(remove), hint="use_comments_or_rag")
        )
        ctx["tools"] = filtered


def is_search_budget_exhausted(tool_name: str, tool_call_log: list[dict[str, Any]]) -> bool:
    """Check whether a search tool has already been called as many times as its per-session budget allows.

    Args:
        tool_name: (str) Tool name to check.
        tool_call_log: (list[dict[str, Any]]) Tool call log to count prior calls in.

    Returns:
        (bool) True if `tool_name` is a search tool and has reached
        _MAX_SEARCH_PER_PLATFORM calls; False for non-search tools."""
    if tool_name not in _SEARCH_TOOLS:
        return False
    return count_tool_name(tool_call_log, tool_name) >= _MAX_SEARCH_PER_PLATFORM


def search_budget_message(
    tool_name: str,
    tool_call_log: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the error payload returned to the model when a search tool's budget is exhausted.

    Suggests a follow-up tool to call instead, and for youtube_search attaches
    the video ids already discovered so the model can proceed without another search.

    Args:
        tool_name: (str) The search tool that was blocked.
        tool_call_log: (list[dict[str, Any]] | None, default None) Prior tool call log,
            used to surface already-found video ids for youtube_search.

    Returns:
        (dict[str, Any]) Dict with "error", "message", "next_tool", and
        (when applicable) "video_ids" fields."""
    follow = "youtube_get_comments_batch" if tool_name == "youtube_search" else "tiktok_comments"
    message = (
        f"Đã gọi {tool_name} đủ lần cho phiên này. "
        f"Dùng {follow} với video_id từ kết quả search trước, hoặc search_movie_summary nếu có RAG."
    )
    out: dict[str, Any] = {
        "error": "search_budget_exhausted",
        "message": message,
        "next_tool": follow,
    }
    if tool_name == "youtube_search" and tool_call_log:
        ids = video_ids_from_log(tool_call_log, tool_name=tool_name)
        if ids:
            out["video_ids"] = ids
            out["message"] = f"{message} Gợi ý video_ids: {ids}"
    return out


def should_force_synthesis(
    tool_call_log: list[dict[str, Any]],
    iteration: int,
    max_iter: int,
) -> bool:
    """True when the agent should stop calling tools and move on to synthesis."""
    if not tool_call_log:
        return False
    if iteration >= max_iter:
        logger.warning(
            log_event(
                "agent",
                "force synthesis",
                reason="max_iterations",
                iteration=iteration,
                max_iterations=max_iter,
                tools=len(tool_call_log),
            )
        )
        return True
    last = tool_call_log[-1]
    last_result = last.get("result") or {}
    last_tool = str(last.get("tool") or "")
    name_repeats = count_last_tool_name(tool_call_log)

    if last_tool in _SEARCH_TOOLS and name_repeats >= _MAX_STUBBORN_SEARCH:
        logger.warning(
            log_event(
                "agent",
                "force synthesis",
                reason="stubborn_search",
                tool=last_tool,
                calls=name_repeats,
            )
        )
        return True

    if last_result.get("error") == "search_budget_exhausted":
        return False

    sig_repeats = count_last_signature(tool_call_log)
    if sig_repeats >= _MAX_SAME_SIGNATURE and last_tool not in _SEARCH_TOOLS:
        logger.warning(
            log_event(
                "agent",
                "force synthesis",
                reason="identical_call",
                tool=last_tool,
                repeats=sig_repeats,
            )
        )
        return True

    if last_tool in _SEARCH_TOOLS:
        return False

    if name_repeats >= _MAX_SAME_TOOL_NAME:
        logger.warning(
            log_event(
                "agent",
                "force synthesis",
                reason="repeated_tool",
                tool=last_tool,
                calls=name_repeats,
            )
        )
        return True

    rounds = len(tool_call_log)
    if has_evidence_data(tool_call_log) and rounds >= _MAX_TOOL_ROUNDS_SOFT:
        logger.warning(
            log_event(
                "agent",
                "force synthesis",
                reason="tool_rounds_with_evidence",
                rounds=rounds,
                limit=_MAX_TOOL_ROUNDS_SOFT,
            )
        )
        return True
    if rounds >= _MAX_TOOL_ROUNDS_NO_EVIDENCE:
        logger.warning(
            log_event(
                "agent",
                "force synthesis",
                reason="tool_rounds_no_evidence",
                rounds=rounds,
                limit=_MAX_TOOL_ROUNDS_NO_EVIDENCE,
            )
        )
        return True
    return False
