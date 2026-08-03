from langgraph.config import get_stream_writer
from langgraph.types import Send
from app.tools.definitions import resolve_tool_set
import app.services.prompts as _prompts
from app.services.agent.domains import DOMAIN_BY_ID, DOMAIN_IDS
from app.services.agent.graph.supervisor import classify_workers_deterministic
from app.services.agent.graph.workers import run_worker_loop
from app.services.agent.synthesis.generate import iter_synthesis_deltas
from app.services.agent.core.context import finish_agent

async def supervisor_node(state: dict) -> dict:
    workers = classify_workers_deterministic(state["task"], state.get("requested_tool_set", "all"))
    if not workers:
        workers = DOMAIN_IDS
    return {"workers_selected": workers}

def route_to_workers(state: dict) -> list[Send]:
    return [
        Send(f"{domain}_worker", {"task": state["task"], "domain": domain, "max_iter": state["max_iter"]})
        for domain in state["workers_selected"]
    ]

async def worker_node(payload: dict) -> dict:
    domain = payload["domain"]
    cfg = DOMAIN_BY_ID[domain]
    tools = await resolve_tool_set(cfg["tool_set"])
    system = f"{_prompts.AGENT_SYSTEM}\n\n{cfg['role_prompt']}"
    log = await run_worker_loop(
        domain=domain, task=payload["task"], tools=tools, system=system, max_iter=payload["max_iter"],
        search_tool=cfg.get("search_tool"), search_arg=cfg.get("search_arg"),
    )
    return {"tool_call_log": log}

async def synthesize_node(state: dict) -> dict:
    if not state["tool_call_log"]:
        return {"final_text": ""}
    # get_stream_writer() an toàn dù chạy qua ainvoke() (no-op) hay astream()
    # (writer() thật sự đẩy chunk ra ngoài) — 1 code path cho cả 2 chế độ.
    writer = get_stream_writer()
    text = ""
    async for delta in iter_synthesis_deltas(
        system=state["system"], task=state["task"], tool_call_log=state["tool_call_log"]
    ):
        text += delta
        if delta:
            writer({"kind": "text_delta", "delta": delta})
    return {"final_text": text}

async def finalize_node(state: dict) -> dict:
    ctx = {"session_id": state.get("session_id", ""), "task": state["task"], "tool_call_log": state["tool_call_log"]}
    result = await finish_agent(ctx, iteration=1, final_text=state.get("final_text", ""))
    return {"result": result}
