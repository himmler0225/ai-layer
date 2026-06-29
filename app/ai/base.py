from __future__ import annotations
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Optional
from app.ai.types import LLMResponse

class BaseLLM(ABC):
    name: str = 'base'

    @abstractmethod
    async def complete(self, *, user_prompt: str, system_prompt: str='', model: Optional[str]=None, max_tokens: Optional[int]=None) -> str:
        pass

    @abstractmethod
    async def complete_json(self, *, user_prompt: str, system_prompt: str='', model: Optional[str]=None, max_tokens: Optional[int]=None) -> str:
        pass

    @abstractmethod
    async def create_response(self, *, model: Optional[str]=None, instructions: Optional[str]=None, input: Any=None, max_output_tokens: Optional[int]=None, tools: Optional[List[Dict]]=None, tool_choice: Optional[str]=None) -> Any:
        pass

    @abstractmethod
    @asynccontextmanager
    async def response_stream(self, **kwargs: Any) -> AsyncIterator[Any]:
        yield

    @abstractmethod
    async def embed_texts(self, texts: List[str], *, model: Optional[str]=None, dimensions: Optional[int]=None) -> List[List[float]]:
        pass
