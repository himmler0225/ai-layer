from app.services.agent.constants import _TIKTOK, _WEB, _YOUTUBE

# Single source of truth for the multi-agent's domain/worker list.
# Adding/removing a domain (e.g. "instagram") only requires editing this array —
# build.py, nodes.py and supervisor.py all derive their domain list and routing
# logic from it, so domain names are never hard-coded anywhere else.
#
# capabilities: the kinds of intent this domain can serve — the supervisor uses
#   this to infer "which domain(s) should intent X route to" instead of
#   hard-coding domain names:
#   - "review": can find/summarize reviews from this domain's source
#   - "catalog": can look up movie metadata/catalog info
#   - "search": external web search (never auto-selected by intent — only via
#     mention_re or an explicit tools="<id>", to avoid calling Tavily (paid) for
#     every vague question when the supervisor falls back to "select all domains")
# mention_re: regex that detects the domain being named in the question (None if
#   the domain has no keyword-based way to be detected, like "movies" — it is
#   selected via the semantic wants_catalog() check instead of by name).
#
# Still required when adding a new domain (unavoidable, since a new domain means
# new capability):
#   1. Define the tools for that domain in app/tools/*_definitions.py
#   2. Add the corresponding key to TOOL_SETS in app/tools/definitions.py
#   3. (Optional) add a dedicated regex (like _YOUTUBE/_TIKTOK) to constants.py
#      and assign it to "mention_re" if you want NLU to auto-detect it by name —
#      otherwise it still works via an explicit tools="<id>".
DOMAINS: list[dict] = [
    {
        "id": "youtube",
        "tool_set": "youtube",
        "role_prompt": "[Vai trò] Bạn là một chuyên gia chuyên tra cứu thông tin trên Youtube - chỉ dùng tool youtube_*, không bàn Tiktok/phim",
        "search_tool": "youtube_search",
        "search_arg": "keyword",
        "capabilities": ["review"],
        "mention_re": _YOUTUBE,
    },
    {
        "id": "tiktok",
        "tool_set": "tiktok",
        "role_prompt": "[Vai trò] Bạn là một chuyên gia chuyên tra cứu thông tin trên Tiktok - chỉ dùng tool tiktok_*, không bàn Youtube/phim",
        "search_tool": "tiktok_search",
        "search_arg": "keyword",
        "capabilities": ["review"],
        "mention_re": _TIKTOK,
    },
    {
        "id": "movies",
        "tool_set": "movies",
        "role_prompt": "[Vai trò] Bạn là một chuyên gia chuyên tra cứu thông tin về phim (kkphim/ophim), không bàn Youtube/Tiktok",
        "search_tool": None,
        "search_arg": None,
        "capabilities": ["catalog"],
        "mention_re": None,
    },
    {
        "id": "web",
        "tool_set": "web",
        "role_prompt": "[Vai trò] Bạn là một chuyên gia tìm kiếm thông tin trên web (Google qua Tavily) - chỉ dùng tool web_*, không bàn Youtube/Tiktok/phim",
        "search_tool": "web_search",
        "search_arg": "query",
        "capabilities": ["search"],
        "mention_re": _WEB,
    },
]

DOMAIN_IDS: list[str] = [d["id"] for d in DOMAINS]
DOMAIN_BY_ID: dict[str, dict] = {d["id"]: d for d in DOMAINS}

# Domains used when the supervisor cannot determine any intent (the "select
# all" fallback) — only includes domains with an intent-based capability
# (review/catalog), NOT "search"-only domains like "web": this avoids calling
# Tavily (paid, rate-limited) for every vague question unrelated to web search.
DEFAULT_FALLBACK_DOMAIN_IDS: list[str] = [
    d["id"] for d in DOMAINS if {"review", "catalog"} & set(d.get("capabilities", ()))
]
