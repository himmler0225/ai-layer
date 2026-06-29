from __future__ import annotations

from typing import Dict

from app.ai.base import BaseLLM
from app.ai.providers import ConfiguredLLM, get_provider_spec, normalize_provider, reset_clients

_instances: Dict[str, BaseLLM] = {}


class LLMFactory:
    @staticmethod
    def get(provider: str) -> BaseLLM:
        key = normalize_provider(provider)
        if key in _instances:
            return _instances[key]
        instance: BaseLLM = ConfiguredLLM(get_provider_spec(key))
        _instances[key] = instance
        return instance

    @staticmethod
    def reset() -> None:
        _instances.clear()
        reset_clients()
