from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any
from collections.abc import AsyncIterator


class BaseLLM(ABC):
    """Lớp `BaseLLM` (kế thừa ABC)."""

    name: str = "base"

    @abstractmethod
    async def complete(
        self, *, user_prompt: str, system_prompt: str = "", model: str | None = None, max_tokens: int | None = None
    ) -> str:
        """Hoàn tất `complete` (async).

        Args:
            user_prompt: (str) Tham số `user_prompt`.
            system_prompt: (str, mặc định '') Tham số `system_prompt`.
            model: (Optional[str], mặc định None) Tham số `model`.
            max_tokens: (Optional[int], mặc định None) Tham số `max_tokens`.

        Returns:
            (str) Kết quả trả về."""
        pass

    @abstractmethod
    async def complete_json(
        self, *, user_prompt: str, system_prompt: str = "", model: str | None = None, max_tokens: int | None = None
    ) -> str:
        """Hoàn tất json (async).

        Args:
            user_prompt: (str) Tham số `user_prompt`.
            system_prompt: (str, mặc định '') Tham số `system_prompt`.
            model: (Optional[str], mặc định None) Tham số `model`.
            max_tokens: (Optional[int], mặc định None) Tham số `max_tokens`.

        Returns:
            (str) Kết quả trả về."""
        pass

    @abstractmethod
    async def create_response(
        self,
        *,
        model: str | None = None,
        instructions: str | None = None,
        input: Any = None,
        max_output_tokens: int | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
    ) -> Any:
        """Tạo response (async).

        Args:
            model: (Optional[str], mặc định None) Tham số `model`.
            instructions: (Optional[str], mặc định None) Tham số `instructions`.
            input: (Any, mặc định None) Tham số `input`.
            max_output_tokens: (Optional[int], mặc định None) Tham số `max_output_tokens`.
            tools: (Optional[List[Dict]], mặc định None) Tham số `tools`.
            tool_choice: (Optional[str], mặc định None) Tham số `tool_choice`.

        Returns:
            (Any) Kết quả trả về."""
        pass

    @abstractmethod
    @asynccontextmanager
    async def response_stream(self, **kwargs: Any) -> AsyncIterator[Any]:
        """Response stream (async).

        Args:
            kwargs: (Any) Tham số `kwargs`.

        Returns:
            (AsyncIterator[Any]) Kết quả trả về."""
        yield

    @abstractmethod
    async def embed_texts(
        self, texts: list[str], *, model: str | None = None, dimensions: int | None = None
    ) -> list[list[float]]:
        """Embed texts (async).

        Args:
            texts: (List[str]) Tham số `texts`.
            model: (Optional[str], mặc định None) Tham số `model`.
            dimensions: (Optional[int], mặc định None) Tham số `dimensions`.

        Returns:
            (List[List[float]]) Kết quả trả về."""
        pass
