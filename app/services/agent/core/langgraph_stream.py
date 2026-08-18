from collections.abc import AsyncGenerator
import uuid

import app.services.prompts as _prompts
from app.config.langfuse import get_langfuse_handler
from app.i18n import msg
from app.services.agent.core.context import video_preview
from app.services.agent.events import data_preview, done, status, text_delta, tool_done, tool_start, tool_status
from app.services.agent.graph.build import get_graph


async def run_agent_multi_stream(task: str, requested_tool_set: str, max_iter: int, system: str | None = None) -> AsyncGenerator[str]:
    """Run the multi-agent graph, mapping its events to SSE strings (same contract as the old run_agent_stream)."""
    graph = get_graph()
    session_id = str(uuid.uuid4())
    initial_state = {
        "session_id": session_id,
        "task": task,
        "system": system or _prompts.AGENT_SYSTEM,
        "max_iter": max_iter,
        "requested_tool_set": requested_tool_set,
        "tool_call_log": [],
    }
    yield status(msg("agent.status.analyzing")).to_sse()

    handler = get_langfuse_handler()
    config = {"callbacks": [handler], "metadata": {"langfuse_session_id": session_id}} if handler else {}

    async for mode, payload in graph.astream(initial_state, config=config, stream_mode=["updates", "custom"]):
        if mode == "custom":
            if payload.get("kind") == "text_delta" and payload.get("delta"):
                yield text_delta(payload["delta"]).to_sse()
                
            if payload.get("kind") == "tool_start":
                args = payload.get("args") or {}
                detail = tool_status(payload["tool"], args)
                yield tool_start(payload["tool"], detail, args, worker=payload.get("worker")).to_sse()
                
            if payload.get("kind") == "tool_done":
                yield tool_done(payload["tool"], worker=payload.get("worker")).to_sse()
                
            continue

        for node_name, partial in payload.items():
            if node_name == "supervisor":
                workers = partial.get("workers_selected") or []
                if workers:
                    yield status(msg("agent.status.researching", domains=", ".join(workers))).to_sse()
                continue
            
            if node_name.endswith("_worker"):
                domain = node_name.removesuffix("_worker")
                log = partial.get("tool_call_log") or []
                preview = video_preview(log)
                if preview:
                    yield data_preview(preview, worker=domain).to_sse()
            elif node_name == "finalize":
                result = partial.get("result")
                if result:
                    if not result.get("tool_calls"):
                        yield status(msg("agent.status.no_results")).to_sse()
                        
                    yield done(result).to_sse()
