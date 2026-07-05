import pytest

from app.ai.adapters import ChatCompletionStreamAdapter
from app.ai.types import FunctionCallItem


class _Fn:
    def __init__(self, name="", arguments=""):
        self.name = name
        self.arguments = arguments


class _ToolCall:
    def __init__(self, *, index=0, id="", name="", arguments=""):
        self.index = index
        self.id = id
        self.function = _Fn(name, arguments)


class _Delta:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _Message:
    def __init__(self, tool_calls=None):
        self.tool_calls = tool_calls


class _Choice:
    def __init__(self, *, delta=None, message=None, finish_reason=None):
        self.delta = delta or _Delta()
        self.message = message
        self.finish_reason = finish_reason


class _Chunk:
    def __init__(self, choice):
        self.choices = [choice]


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = chunks

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_stream_adapter_reads_message_tool_calls():
    chunks = [
        _Chunk(_Choice(delta=_Delta(), finish_reason=None)),
        _Chunk(
            _Choice(
                delta=_Delta(),
                message=_Message(
                    tool_calls=[_ToolCall(index=0, id="call_1", name="movie_get_metadata", arguments='{"kind":"genres"}')]
                ),
                finish_reason="tool_calls",
            )
        ),
    ]
    adapter = ChatCompletionStreamAdapter(_FakeStream(chunks))
    async for _ in adapter:
        pass
    final = await adapter.get_final_response()
    assert len(final.output) == 1
    assert isinstance(final.output[0], FunctionCallItem)
    assert final.output[0].name == "movie_get_metadata"
