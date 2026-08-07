from app.ai.base import BaseLLM
from app.ai.providers import ConfiguredLLM, get_provider_spec, normalize_provider, reset_clients

_instances: dict[str, BaseLLM] = {}


class LLMFactory:
    """Factory that creates and caches one LLM client instance per provider name."""

    @staticmethod
    def get(provider: str) -> BaseLLM:
        """Get the cached LLM client for a provider, creating it on first use.

        Args:
            provider: Provider name (openai, deepseek, xai, ...).

        Returns:
            The cached or newly created `BaseLLM` instance for this provider."""
        key = normalize_provider(provider)
        if key in _instances:
            return _instances[key]
        instance: BaseLLM = ConfiguredLLM(get_provider_spec(key))
        _instances[key] = instance
        return instance

    @staticmethod
    def reset() -> None:
        """Clear all cached LLM instances and reset the underlying HTTP clients."""
        _instances.clear()
        reset_clients()
