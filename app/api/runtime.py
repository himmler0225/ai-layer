import json

from fastapi import APIRouter, Depends

from app.auth.config_admin import load_config
from app.config.loader import _normalize_provider_map, resolve_active_provider
from app.middleware.auth import verify_api_key
from app.schemas.response import ApiResponse

router = APIRouter(prefix="/runtime", dependencies=[Depends(verify_api_key)])

DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant that can answer questions and help with tasks"


def _parse_system_prompt(prompts_raw: str) -> str:
    """(Nội bộ) Phân tích system prompt `_parse_system_prompt`.

    Args:
        prompts_raw: (str) Tham số `prompts_raw`.

    Returns:
        (str) Kết quả trả về."""
    if not prompts_raw.strip():
        return DEFAULT_SYSTEM_PROMPT
    try:
        prompts = json.loads(prompts_raw)
    except json.JSONDecodeError:
        return DEFAULT_SYSTEM_PROMPT
    agent_system = (prompts.get("agent") or {}).get("system")
    if isinstance(agent_system, str) and agent_system.strip():
        return agent_system.strip()
    return DEFAULT_SYSTEM_PROMPT


@router.get("/chat-config")
async def chat_config():
    """Runtime chat config for BFF — active provider + system prompt."""
    config = await load_config()

    models_raw = config.get("AI_MODELS", "")
    models_data: dict | list = {}
    if models_raw.strip():
        try:
            parsed = json.loads(models_raw)
            if isinstance(parsed, (dict, list)):
                models_data = parsed
        except json.JSONDecodeError:
            models_data = {}

    provider_map = _normalize_provider_map(models_data)
    active_id = resolve_active_provider(models_data)

    active_provider = None
    if active_id and active_id in provider_map:
        cfg = provider_map[active_id]
        if isinstance(cfg, dict):
            active_provider = {
                "id": active_id,
                "api_key": cfg.get("api_key"),
                "base_url": cfg.get("base_url"),
                "model": cfg.get("model"),
                "max_tokens": cfg.get("max_tokens"),
            }

    system_prompt = _parse_system_prompt(config.get("PROMPTS", ""))

    return ApiResponse.ok(
        {
            "activeProvider": active_provider,
            "systemPrompt": system_prompt,
            "supportsWebSearch": active_id == "openai",
        }
    )
