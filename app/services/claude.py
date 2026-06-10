import anthropic
from typing import Optional
from app.config.settings import ANTHROPIC_API_KEY, CLAUDE_MODEL, CLAUDE_MAX_TOKENS

_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


async def complete(
    user_prompt: str,
    system_prompt: str,
    max_tokens: int = CLAUDE_MAX_TOKENS,
    model: str = CLAUDE_MODEL,
) -> str:
    msg = await _client.messages.create(
        model=model,
        max_tokens=max_tokens,
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
    max_tokens: int = CLAUDE_MAX_TOKENS,
    model: str = CLAUDE_MODEL,
) -> str:
    """Same as complete() but instructs the model to return valid JSON only."""
    system_with_json = system_prompt + "\n\nRespond with valid JSON only. No markdown, no explanation."
    return await complete(user_prompt, system_with_json, max_tokens, model)
