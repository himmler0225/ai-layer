from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any
from collections.abc import AsyncIterator


class BaseLLM(ABC):
    """Abstract interface that every LLM provider adapter must implement:
    plain text completion, JSON completion, Responses-API-style
    request/response and streaming, and text embedding."""

    name: str = "base"

    @abstractmethod
    async def complete(
        self, *, user_prompt: str, system_prompt: str = "", model: str | None = None, max_tokens: int | None = None
    ) -> str:
        """Run a single-turn text completion.

        Args:
            user_prompt: The user's message content.
            system_prompt: Optional system instructions; omitted if empty.
            model: Model name override; provider's default model if `None`.
            max_tokens: Max output tokens; provider's default if `None`.

        Returns:
            The generated text, stripped of leading/trailing whitespace."""
        pass

    @abstractmethod
    async def complete_json(
        self, *, user_prompt: str, system_prompt: str = "", model: str | None = None, max_tokens: int | None = None
    ) -> str:
        """Run a completion constrained to return valid JSON.

        Args:
            user_prompt: The user's message content.
            system_prompt: Optional system instructions; omitted if empty.
            model: Model name override; provider's default model if `None`.
            max_tokens: Max output tokens; provider's default if `None`.

        Returns:
            The generated text as a JSON string (not yet parsed)."""
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
        tool_choice: str | dict[str, Any] | None = None,
    ) -> Any:
        """Run a Responses-API-style completion, optionally with tool calling.

        Args:
            model: Model name override; provider's default model if `None`.
            instructions: Optional system-level instructions.
            input: Conversation input (Responses-API items or plain string).
            max_output_tokens: Max output tokens; provider's default if `None`.
            tools: Optional list of tool/function definitions to expose.
            tool_choice: Optional tool-choice directive (e.g. `"auto"` or a
                specific tool spec).

        Returns:
            A provider-specific response object (e.g. `LLMResponse`)."""
        pass

    @abstractmethod
    @asynccontextmanager
    async def response_stream(self, **kwargs: Any) -> AsyncIterator[Any]:
        """Run a streaming completion as an async context manager.

        Args:
            kwargs: Same parameters as `create_response` (model, instructions,
                input, max_output_tokens, tools, tool_choice), passed through
                by the concrete implementation.

        Returns:
            An async iterator/context yielding stream events, ending with a
            way to obtain the final aggregated response."""
        yield

    @abstractmethod
    async def embed_texts(
        self, texts: list[str], *, model: str | None = None, dimensions: int | None = None
    ) -> list[list[float]]:
        """Generate embedding vectors for a batch of texts.

        Args:
            texts: Texts to embed; an empty list yields an empty result.
            model: Embedding model override; provider's default if `None`.
            dimensions: Optional requested embedding dimensionality.

        Returns:
            One embedding vector (list of floats) per input text, in order.
            Implementations may raise if the provider doesn't support
            embeddings."""
        pass
