"""Factory — tạo provider theo tên."""

from __future__ import annotations

from typing import Dict

from app.ai.base import BaseLLM
from app.ai.deepseek_provider import DeepSeekProvider
from app.ai.openai_provider import OpenAIProvider

_providers: Dict[str, BaseLLM] = {}


class LLMFactory:
    @staticmethod
    def get(provider: str) -> BaseLLM:
        key = (provider or "").strip().lower()
        if key in _providers:
            return _providers[key]

        if key == "openai":
            instance: BaseLLM = OpenAIProvider()
        elif key in ("deepseek", "deep_seek"):
            instance = DeepSeekProvider()
        else:
            raise ValueError(f"LLM provider not found: {provider}")

        _providers[key] = instance
        return instance

    @staticmethod
    def reset() -> None:
        """Xóa cache — dùng trong test."""
        _providers.clear()
