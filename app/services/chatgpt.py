from typing import Optional

from app.utils.openai_client import get_openai_client

import app.config.settings as _cfg

async def complete(
    user_prompt: str,
    system_prompt: str,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
) -> str:
    client = get_openai_client()
    inputs = []

    if system_prompt:
        inputs.append({
            "role": "system",
            "content": system_prompt
        })

    inputs.append({
        "role": "user",
        "content": user_prompt
    })

    response = await client.responses.create(
        model=model or _cfg.OPENAI_MODEL,
        input=inputs,
        max_output_tokens=max_tokens or _cfg.OPENAI_MAX_TOKENS,
    )

    return response.output_text

async def complete_json(
    user_prompt: str,
    system_prompt: str,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
) -> str:
    system_with_json = system_prompt + "\n\nRespond with valid JSON only. No markdown, no explanation."
    return await complete(user_prompt, system_with_json, max_tokens, model)
