import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import APIStatusError

from app.services.agent.engine import process_agent_step, tool_round_action
from app.services.agent.synthesis import (
    _is_stream_open_failure,
    _should_fallback_synth,
    iter_synthesis_deltas,
    synth_models_to_try,
)
from app.utils.llm_errors import is_upstream_gateway_error, user_message


@pytest.mark.asyncio
async def test_process_agent_step_continue_after_tools():
    ctx = {
        "max_iter": 8,
        "tool_call_log": [
            {
                "tool": "youtube_search",
                "inputs": {"keyword": "iphone"},
                "result": {"results": [{"video_id": "abc"}]},
            }
        ],
        "input_items": [],
        "tools": [{"name": "youtube_get_comments_batch"}],
        "session_id": "s",
        "task": "review iphone",
        "system": "sys",
    }
    call = MagicMock()
    call.type = "function_call"
    call.name = "youtube_get_comments_batch"
    call.arguments = '{"video_ids": ["abc"]}'
    call.call_id = "c1"
    response = MagicMock()
    response.status = "completed"
    response.output = [call]

    with patch(
        "app.services.agent.tools.execute_parallel",
        new_callable=AsyncMock,
        return_value=(
            [{"type": "function_call_output", "call_id": "c1", "output": "{}"}],
            [
                {
                    "tool": "youtube_get_comments_batch",
                    "inputs": {"video_ids": ["abc"]},
                    "result": {"comments": [{"content": "good"}]},
                }
            ],
        ),
    ):
        outcome = await process_agent_step(ctx, response, iteration=1)

    assert outcome.action == "continue"
    assert len(ctx["tool_call_log"]) == 2


def test_tool_round_action_force_on_stubborn_search():
    ctx = {
        "tool_call_log": [
            {"tool": "youtube_search", "inputs": {}, "result": {}},
        ]
        + [
            {
                "tool": "youtube_search",
                "inputs": {"k": i},
                "result": {"error": "search_budget_exhausted"},
            }
            for i in range(3)
        ],
        "max_iter": 8,
    }
    assert tool_round_action(ctx, iteration=4) == "force_synthesis"


def test_tool_round_action_continue_after_budget_block():
    ctx = {
        "tool_call_log": [
            {"tool": "youtube_search", "inputs": {}, "result": {"results": []}},
            {"tool": "youtube_search", "inputs": {}, "result": {"error": "search_budget_exhausted"}},
        ],
        "max_iter": 8,
    }
    assert tool_round_action(ctx, iteration=2) == "continue"


def test_synth_models_includes_fallback_when_different(monkeypatch):
    import app.services.agent.config as cfg

    monkeypatch.setattr(cfg, "synth_model", lambda: "big-model")
    monkeypatch.setattr(cfg, "tool_model", lambda: "small-model")
    assert synth_models_to_try() == ["big-model", "small-model"]


def _make_status_error(code: int, body=None) -> APIStatusError:
    request = MagicMock()
    response = MagicMock()
    response.status_code = code
    response.request = request
    return APIStatusError(str(code), response=response, body=body or {})


def test_should_fallback_on_502(monkeypatch):
    import app.services.agent.config as cfg

    monkeypatch.setattr(cfg, "tool_model", lambda: "fallback")
    exc = _make_status_error(502)
    assert is_upstream_gateway_error(exc)
    assert _should_fallback_synth(exc, "primary-model") is True
    assert _should_fallback_synth(exc, "fallback") is False


def test_user_message_502_mentions_gateway():
    exc = _make_status_error(502, {"error": {"message": "AI gateway upstream đang lỗi."}})
    msg = user_message(exc)
    assert "502" in msg


def test_is_stream_open_failure():
    assert _is_stream_open_failure(json.JSONDecodeError("Expecting value", "", 0)) is True
    assert _is_stream_open_failure(ValueError("Expecting value: line 1 column 1 (char 0)")) is True
    assert _is_stream_open_failure(RuntimeError("timeout")) is False


@pytest.mark.asyncio
async def test_iter_synthesis_deltas_falls_back_to_non_stream(monkeypatch):
    import app.services.agent.config as cfg

    monkeypatch.setattr(cfg, "synth_model", lambda: "big-model")
    monkeypatch.setattr(cfg, "tool_model", lambda: "small-model")
    monkeypatch.setattr(cfg, "synth_max_tokens", lambda: 1024)

    stream_ctx = AsyncMock()
    stream_ctx.__aenter__.return_value = _empty_async_iter()
    stream_ctx.__aexit__.return_value = None

    with patch(
        "app.services.agent.synthesis.response_stream",
        return_value=stream_ctx,
    ) as mock_stream:
        mock_stream.side_effect = json.JSONDecodeError("Expecting value", "", 0)
        with patch(
            "app.services.agent.synthesis.run_synthesis",
            new_callable=AsyncMock,
            return_value="final answer",
        ) as mock_run:
            chunks = [
                delta
                async for delta in iter_synthesis_deltas(
                    system="sys",
                    task="hello",
                    tool_call_log=[{"tool": "t", "inputs": {}, "result": {"ok": True}}],
                )
            ]

    assert chunks == ["final answer"]
    assert mock_run.await_count == 1


async def _empty_async_iter():
    if False:
        yield ""
