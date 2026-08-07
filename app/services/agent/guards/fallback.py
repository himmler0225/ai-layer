"""Deterministic tool fallback when the LLM returns empty on catalog queries."""

import json
import re
import uuid
from typing import Any

from app.ai.types import FunctionCallItem
from app.rag.movie_hint import context_for_filtering, conversation_history, current_question, wants_catalog

_GENRE_SLUGS: dict[str, str] = {
    "tình cảm": "tinh-cam",
    "tinhcam": "tinh-cam",
    "lãng mạn": "tinh-cam",
    "hành động": "hanh-dong",
    "kinh dị": "kinh-di",
    "hài": "hai-huoc",
    "viễn tưởng": "vien-tuong",
    "hoạt hình": "hoat-hinh",
    "tâm lý": "tam-ly",
    "phiêu lưu": "phieu-luu",
    "bí ẩn": "bi-an",
    "gia đình": "gia-dinh",
    "chính kịch": "chinh-kich",
    "cổ trang": "co-trang",
    "hình sự": "hinh-su",
}

_COUNTRY_SLUGS: dict[str, str] = {
    "trung quốc": "trung-quoc",
    "trung": "trung-quoc",
    "china": "trung-quoc",
    "hàn quốc": "han-quoc",
    "hàn": "han-quoc",
    "korea": "han-quoc",
    "mỹ": "au-my",
    "usa": "au-my",
    "nhật": "nhat-ban",
    "japan": "nhat-ban",
    "thái": "thai-lan",
    "việt": "viet-nam",
    "đài": "dai-loan",
    "ấn độ": "an-do",
    "anh": "anh",
    "pháp": "phap",
}


def _task_text(task: str) -> str:
    """(Internal) Get the text to scan for catalog intent/genre/country signals, falling back to conversation history.

    Args:
        task: (str) Raw task string, possibly containing conversation history and the current question.

    Returns:
        (str) The filtering context or current question extracted from `task`;
        if that alone doesn't carry catalog intent, the conversation history is
        merged in when doing so reveals catalog intent (short follow-ups like
        "not enough, give me more" don't restate genre/country on their own)."""
    text = context_for_filtering(task) or current_question(task) or (task or "")
    # Short follow-ups like "not enough, give me more movies" don't restate the
    # genre/country — if the current sentence lacks catalog signal, merge in the
    # history to look for a slug.
    if not wants_catalog(text):
        history = conversation_history(task)
        if history:
            merged = f"{history}\n\n{text}"
            if wants_catalog(merged):
                return merged
    return text


def _tool_names(tools: list[dict]) -> set[str]:
    """(Internal) Collect the set of tool names available in a tool definitions list.

    Args:
        tools: (list[dict]) Tool definitions, each expected to carry a "name" key.

    Returns:
        (set[str]) Non-empty tool names found in `tools`."""
    return {t.get("name", "") for t in tools if t.get("name")}


def _match_slug(text: str, mapping: dict[str, str]) -> str | None:
    """(Internal) Find the slug for the longest matching label found in text.

    Args:
        text: (str) Text to search (matched case-insensitively).
        mapping: (dict[str, str]) Label -> slug mapping (e.g. genre or country names to slugs).

    Returns:
        (str | None) The slug for the longest label present in `text`, or None if no label matches."""
    lowered = text.lower()
    for label, slug in sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True):
        if label in lowered:
            return slug
    return None


def catalog_forced_tool_choice(task: str, tools: list[dict]) -> dict[str, Any] | None:
    """OpenAI-style tool_choice forcing one catalog function."""
    if not wants_catalog(_task_text(task)):
        return None
    names = _tool_names(tools)
    text = _task_text(task)
    genre = _match_slug(text, _GENRE_SLUGS)
    country = _match_slug(text, _COUNTRY_SLUGS)

    if genre and "movie_list_by_genre" in names:
        return {"type": "function", "function": {"name": "movie_list_by_genre"}}
    if country and "movie_list_by_country" in names:
        return {"type": "function", "function": {"name": "movie_list_by_country"}}
    if "movie_get_metadata" in names:
        return {"type": "function", "function": {"name": "movie_get_metadata"}}
    for name in sorted(names):
        if name.startswith("movie_"):
            return {"type": "function", "function": {"name": name}}
    return None


def catalog_fallback_call(task: str, tools: list[dict]) -> FunctionCallItem | None:
    """Build a synthetic tool call when the LLM stays silent on catalog intent."""
    text = _task_text(task)
    if not wants_catalog(text):
        return None
    names = _tool_names(tools)
    genre = _match_slug(text, _GENRE_SLUGS)
    country = _match_slug(text, _COUNTRY_SLUGS)
    provider = "kkphim"
    call_id = f"fallback_{uuid.uuid4().hex[:12]}"

    if genre and "movie_list_by_genre" in names:
        args: dict[str, Any] = {"slug": genre, "provider": provider, "limit": 10, "page": 1}
        if country:
            args["country"] = country
        return FunctionCallItem(call_id=call_id, name="movie_list_by_genre", arguments=json.dumps(args))

    if country and "movie_list_by_country" in names:
        args = {"slug": country, "provider": provider, "limit": 10, "page": 1}
        if genre:
            args["category"] = genre
        return FunctionCallItem(call_id=call_id, name="movie_list_by_country", arguments=json.dumps(args))

    if re.search(r"\bphim mới\b", text, re.IGNORECASE) and "movie_list_new" in names:
        return FunctionCallItem(
            call_id=call_id,
            name="movie_list_new",
            arguments=json.dumps({"provider": provider, "page": 1}),
        )

    year_match = re.search(r"\b(19|20)\d{2}\b", text)
    if year_match and "movie_list_by_year" in names:
        return FunctionCallItem(
            call_id=call_id,
            name="movie_list_by_year",
            arguments=json.dumps({"year": int(year_match.group(0)), "provider": provider, "limit": 10}),
        )

    search_match = re.search(r'(?:tìm|search)\s+["\u201c]?([^"\u201d\n,.?!]{2,60})', text, re.IGNORECASE)
    if search_match and "movie_search" in names:
        return FunctionCallItem(
            call_id=call_id,
            name="movie_search",
            arguments=json.dumps({"keyword": search_match.group(1).strip(), "provider": provider, "limit": 10}),
        )

    if "movie_get_metadata" in names:
        kind = "countries" if country and not genre else "genres"
        return FunctionCallItem(
            call_id=call_id,
            name="movie_get_metadata",
            arguments=json.dumps({"kind": kind, "provider": provider}),
        )

    for name in sorted(names):
        if name.startswith("movie_"):
            return FunctionCallItem(call_id=call_id, name=name, arguments="{}")
    return None
