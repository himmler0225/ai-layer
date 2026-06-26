"""Client LLM — re-export từ Factory (backward compat)."""

from openai import AsyncOpenAI

import app.config.settings as _cfg
from app.ai.factory import LLMFactory
from app.ai.openai_provider import _get_client as _openai_sdk_client
from app.ai.deepseek_provider import _get_client as _deepseek_sdk_client


def get_openai_client() -> AsyncOpenAI:
    """Singleton AsyncOpenAI — dùng khi cần SDK trực tiếp."""
    LLMFactory.get("openai")
    return _openai_sdk_client()


def get_deepseek_client() -> AsyncOpenAI:
    """Singleton AsyncOpenAI (DeepSeek base_url)."""
    LLMFactory.get("deepseek")
    return _deepseek_sdk_client()
