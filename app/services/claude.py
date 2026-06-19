from typing import Optional

import anthropic

import app.config.settings as _cfg

_client: Optional[anthropic.AsyncAnthropic] = None

def _get_client() -> anthropic.AsyncAnthropic:
    # Lazily built so the Supabase-loaded ANTHROPIC_API_KEY is in effect.
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=_cfg.ANTHROPIC_API_KEY)
    return _client

async def complete(
    user_prompt: str,
    system_prompt: str,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
) -> str:
    msg = await _get_client().messages.create(
        model=model or _cfg.CLAUDE_MODEL,
        max_tokens=max_tokens or _cfg.CLAUDE_MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},  # prompt caching
            }
        ],
        messages=[{"role": "user", "content": user_prompt}],
    )
    return msg.content[0].text

async def complete_json(
    user_prompt: str,
    system_prompt: str,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
) -> str:
    system_with_json = system_prompt + "\n\nRespond with valid JSON only. No markdown, no explanation."
    return await complete(user_prompt, system_with_json, max_tokens, model)
