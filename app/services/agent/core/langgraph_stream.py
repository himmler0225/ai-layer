import uuid

import app.services.prompts as _prompts
from app.i18n import both
from app.services.agent.core.context import video_preview
from app.services.agent.events import data_preview, done, status, text_delta, tool_done, tool_start, tool_status
from app.services.agent.graph.build import get_graph


async def run_agent_multi_stream(task: str, requested_tool_set: str, max_iter: int, system: str | None = None):
    """Chạy agent multi-agent, map sự kiện graph -> chuỗi SSE (cùng contract run_agent_stream cũ)."""
    graph = get_graph()
    initial_state = {
        "session_id": str(uuid.uuid4()),
        "task": task,
        "system": system or _prompts.AGENT_SYSTEM,
        "max_iter": max_iter,
        "requested_tool_set": requested_tool_set,
        "tool_call_log": [],
    }
    yield status(*both("agent.status.analyzing")).to_sse()

    async for mode, payload in graph.astream(initial_state, stream_mode=["updates", "custom"]):
        if mode == "custom":
            if payload.get("kind") == "text_delta" and payload.get("delta"):
                yield text_delta(payload["delta"]).to_sse()
            continue

        # mode == "updates": {node_name: partial_state_vừa_trả_về}
        for node_name, partial in payload.items():
            if node_name.endswith("_worker"):
                domain = node_name.removesuffix("_worker")
                log = partial.get("tool_call_log") or []
                for entry in log:
                    name = entry.get("tool") or ""
                    args = entry.get("inputs") or {}
                    vi, en = tool_status(name, args)
                    yield tool_start(name, vi, en, args, worker=domain).to_sse()
                    yield tool_done(name, worker=domain).to_sse()
                preview = video_preview(log)
                if preview:
                    yield data_preview(preview, worker=domain).to_sse()
            elif node_name == "finalize":
                result = partial.get("result")
                if result:
                    yield done(result).to_sse()
