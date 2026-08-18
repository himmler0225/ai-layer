from unittest.mock import patch, MagicMock

import pytest

from app.services.agent.core.langgraph_stream import run_agent_multi_stream

async def _fake_astream(initial_state, config=None, stream_mode=None):
    # worker.py now reports tool_start/tool_done LIVE via "custom" (get_stream_writer),
    # before the tool actually finishes running — no longer via "updates".
    yield ("custom", {"kind": "tool_start", "worker": "youtube", "tool": "youtube_search", "args": {"keyword": "abc"}})
    yield ("custom", {"kind": "tool_done", "worker": "youtube", "tool": "youtube_search"})
    yield ("updates", {"youtube_worker": {"tool_call_log": [
        {"tool": "youtube_search", "inputs": {"keyword": "abc"}, "result": {}}
    ]}})
    yield ("custom", {"kind": "text_delta", "delta": "Xin chào"})
    yield ("updates", {"finalize": {"result": {"data": {}, "tool_calls": [{"tool": "youtube_search"}]}}})

@pytest.mark.asyncio
async def test_stream_maps_worker_and_finalize_events():
    fake_graph = MagicMock()
    fake_graph.astream = _fake_astream
    with patch("app.services.agent.core.langgraph_stream.get_graph", return_value=fake_graph):
        events = [e async for e in run_agent_multi_stream("task", "all", 10)]
    tool_start_events = [e for e in events if '"type": "tool_start"' in e]
    assert len(tool_start_events) == 1  
    
    assert '"worker": "youtube"' in tool_start_events[0]
    assert any('"type": "text_delta"' in e for e in events)
    assert events[-1].startswith('data: {"type": "done"')
