import json
from typing import Any

from app.config.logger import Logger

logger = Logger.get(__name__)

# Cùng tool + input giống hệt (tool không phải search).
_MAX_SAME_SIGNATURE = 2
# Cùng tên tool (keyword khác) — áp dụng tool không phải search.
_MAX_SAME_TOOL_NAME = 2
# Tổng số lần gọi tool bất kỳ trước khi ép synthesis (khi đã có dữ liệu).
_MAX_TOOL_ROUNDS_SOFT = 6
# Vòng thêm khi chưa có comments/transcript/RAG.
_MAX_TOOL_ROUNDS_NO_EVIDENCE = 10
# Model vẫn gọi search sau khi bị chặn budget.
_MAX_STUBBORN_SEARCH = 4

_SEARCH_TOOLS: set[str] = frozenset({"youtube_search", "tiktok_search"})
# Mỗi nền tảng chỉ search tối đa 1 lần; lần sau gỡ khỏi menu tool.
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
    """Tool signature.

    Args:
        name: (str) Tham số `name`.
        inputs: (dict[str, Any]) Tham số `inputs`.

    Returns:
        (str) Kết quả trả về."""
    try:
        payload = json.dumps(inputs or {}, sort_keys=True, ensure_ascii=False)
    except TypeError:
        payload = "{}"
    return f"{name}:{payload}"


def count_tool_name(log: list[dict[str, Any]], name: str) -> int:
    """Count tool name.

    Args:
        log: (list[dict[str, Any]]) Tham số `log`.
        name: (str) Tham số `name`.

    Returns:
        (int) Kết quả trả về."""
    return sum(1 for entry in log if entry.get("tool") == name)


def is_budget_block(entry: dict[str, Any]) -> bool:
    """Is budget block.

    Args:
        entry: (dict[str, Any]) Tham số `entry`.

    Returns:
        (bool) Kết quả trả về."""
    result = entry.get("result") or {}
    return result.get("error") == "search_budget_exhausted"


def _result_payload(result: Any) -> dict[str, Any]:
    """(Nội bộ) Result payload `_result_payload`.

    Args:
        result: (Any) Tham số `result`.

    Returns:
        (dict[str, Any]) Kết quả trả về."""
    if not isinstance(result, dict):
        return {}
    data = result.get("data")
    if isinstance(data, dict):
        return data
    return result


def extract_video_items(result: Any) -> list[dict[str, Any]]:
    """Trích xuất video items.

    Args:
        result: (Any) Tham số `result`.

    Returns:
        (list[dict[str, Any]]) Kết quả trả về."""
    payload = _result_payload(result)
    for key in ("results", "videos", "items"):
        items = payload.get(key)
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


def video_ids_from_log(log: list[dict[str, Any]], *, tool_name: str = "youtube_search") -> list[str]:
    """Video ids from log.

    Args:
        log: (list[dict[str, Any]]) Tham số `log`.
        tool_name: (str, mặc định 'youtube_search') Tham số `tool_name`.

    Returns:
        (list[str]) Kết quả trả về."""
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
    """Has evidence data.

    Args:
        log: (list[dict[str, Any]]) Tham số `log`.

    Returns:
        (bool) Kết quả trả về."""
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
    """Count last signature.

    Args:
        log: (list[dict[str, Any]]) Tham số `log`.

    Returns:
        (int) Kết quả trả về."""
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
    """Count last tool name.

    Args:
        log: (list[dict[str, Any]]) Tham số `log`.

    Returns:
        (int) Kết quả trả về."""
    if not log:
        return 0
    name = str(log[-1].get("tool") or "")
    return count_tool_name(log, name)


def apply_tool_budget(ctx: dict[str, Any]) -> None:
    """Sau mỗi vòng tool: bỏ search tool đã dùng đủ để model chuyển sang comments/RAG."""
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
        logger.info("[agent] tool budget: removed %s (use comments/RAG next)", sorted(remove))
        ctx["tools"] = filtered


def is_search_budget_exhausted(tool_name: str, tool_call_log: list[dict[str, Any]]) -> bool:
    """Is search budget exhausted.

    Args:
        tool_name: (str) Tham số `tool_name`.
        tool_call_log: (list[dict[str, Any]]) Tham số `tool_call_log`.

    Returns:
        (bool) Kết quả trả về."""
    if tool_name not in _SEARCH_TOOLS:
        return False
    return count_tool_name(tool_call_log, tool_name) >= _MAX_SEARCH_PER_PLATFORM


def search_budget_message(
    tool_name: str,
    tool_call_log: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Search budget message.

    Args:
        tool_name: (str) Tham số `tool_name`.
        tool_call_log: (list[dict[str, Any]] | None, mặc định None) Tham số `tool_call_log`.

    Returns:
        (dict[str, Any]) Kết quả trả về."""
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
    """True khi nên dừng gọi tool và chuyển sang synthesis."""
    if not tool_call_log:
        return False
    if iteration >= max_iter:
        logger.warning(
            "[agent] force synthesis: max_iter iter=%d/%d tools=%d",
            iteration,
            max_iter,
            len(tool_call_log),
        )
        return True
    last = tool_call_log[-1]
    last_result = last.get("result") or {}
    last_tool = str(last.get("tool") or "")
    name_repeats = count_last_tool_name(tool_call_log)

    if last_tool in _SEARCH_TOOLS and name_repeats >= _MAX_STUBBORN_SEARCH:
        logger.warning(
            "[agent] force synthesis: stubborn search tool=%s calls=%d",
            last_tool,
            name_repeats,
        )
        return True

    if last_result.get("error") == "search_budget_exhausted":
        return False

    sig_repeats = count_last_signature(tool_call_log)
    if sig_repeats >= _MAX_SAME_SIGNATURE and last_tool not in _SEARCH_TOOLS:
        logger.warning(
            "[agent] force synthesis: identical call x%d tool=%s",
            sig_repeats,
            last_tool,
        )
        return True

    if last_tool in _SEARCH_TOOLS:
        return False

    if name_repeats >= _MAX_SAME_TOOL_NAME:
        logger.warning(
            "[agent] force synthesis: tool name %s called %d times",
            last_tool,
            name_repeats,
        )
        return True

    rounds = len(tool_call_log)
    if has_evidence_data(tool_call_log) and rounds >= _MAX_TOOL_ROUNDS_SOFT:
        logger.warning(
            "[agent] force synthesis: tool rounds=%d >= %d (has evidence)",
            rounds,
            _MAX_TOOL_ROUNDS_SOFT,
        )
        return True
    if rounds >= _MAX_TOOL_ROUNDS_NO_EVIDENCE:
        logger.warning(
            "[agent] force synthesis: tool rounds=%d >= %d (no evidence)",
            rounds,
            _MAX_TOOL_ROUNDS_NO_EVIDENCE,
        )
        return True
    return False
