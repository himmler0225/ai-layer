from __future__ import annotations
import sys
import httpx
from app.config.settings import SUPABASE_URL, SUPABASE_SERVICE_KEY

_REMOTABLE_STR = frozenset({
    "ANTHROPIC_API_KEY", "CLAUDE_MODEL", "DATA_MINER_KEY",
    "PROXY_URL", "PROXY_USERNAME", "PROXY_PASSWORD",
})
_PROMPT_KEY = "AGENT_SYSTEM"
_REMOTABLE_INT = frozenset({
    "CLAUDE_MAX_TOKENS", "AGENT_MAX_ITER",
    "AGENT_MAX_RESULT_CHARS", "AGENT_MAX_COMMENTS",
    "AGENT_MAX_COMMENT_LEN", "AGENT_MAX_LIST_ITEMS",
})

async def load_and_apply() -> None:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                f"{SUPABASE_URL}/rest/v1/config",
                params={"select": "key,value"},
                headers={
                    "apikey":        SUPABASE_SERVICE_KEY,
                    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                },
            )
            if not r.is_success:
                return
            remote: dict[str, str] = {
                row["key"]: row["value"]
                for row in r.json()
                if row.get("value")
            }
    except Exception:
        return

    settings = sys.modules["app.config.settings"]

    for key in _REMOTABLE_STR:
        if remote.get(key):
            setattr(settings, key, remote[key])

    for key in _REMOTABLE_INT:
        if remote.get(key):
            try:
                setattr(settings, key, int(remote[key]))
            except ValueError:
                pass

    if remote.get(_PROMPT_KEY):
        prompts = sys.modules.get("app.services.prompts")
        if prompts:
            setattr(prompts, "AGENT_SYSTEM", remote[_PROMPT_KEY])
