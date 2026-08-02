import uuid

import app.services.prompts as _prompts
from app.services.agent.graph.build import get_graph


async def run_agent_multi(task: str, requested_tool_set: str, max_iter: int, system: str | None = None) -> dict:
    graph = get_graph()
    initial_state = {
        "session_id": str(uuid.uuid4()),
        "task": task,
        "system": system or _prompts.AGENT_SYSTEM,
        "max_iter": max_iter,
        "requested_tool_set": requested_tool_set,
        "tool_call_log": [],
    }
    final_state = await graph.ainvoke(initial_state)
    return final_state["result"]
