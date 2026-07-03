from app.ai.base import BaseLLM
from app.ai.providers import ConfiguredLLM, get_provider_spec, normalize_provider, reset_clients

_instances: dict[str, BaseLLM] = {}


class LLMFactory:
    """Factory tạo và cache client LLM theo tên provider."""

    @staticmethod
    def get(provider: str) -> BaseLLM:
        """Lấy hoặc tạo client LLM cho provider.

        Args:
            provider: Tên provider (openai, deepseek, xah, ...).

        Returns:
            Instance LLM đã cache hoặc mới khởi tạo."""
        key = normalize_provider(provider)
        if key in _instances:
            return _instances[key]
        instance: BaseLLM = ConfiguredLLM(get_provider_spec(key))
        _instances[key] = instance
        return instance

    @staticmethod
    def reset() -> None:
        """Xóa cache instance LLM và reset HTTP client nội bộ."""
        _instances.clear()
        reset_clients()
