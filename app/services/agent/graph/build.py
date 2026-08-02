from langgraph.graph import StateGraph, END
from app.services.agent.domains import DOMAIN_IDS
from app.services.agent.graph.state import AgentState
from app.services.agent.graph.nodes import (
    supervisor_node, route_to_workers, worker_node,
    synthesize_node, finalize_node,
)

def build_multi_agent_graph():
    g = StateGraph(AgentState)
    g.add_node("supervisor", supervisor_node)
    for domain_id in DOMAIN_IDS:
        g.add_node(f"{domain_id}_worker", worker_node)
    g.add_node("synthesize", synthesize_node)
    g.add_node("finalize", finalize_node)

    g.set_entry_point("supervisor")
    g.add_conditional_edges("supervisor", route_to_workers)
    for domain_id in DOMAIN_IDS:
        g.add_edge(f"{domain_id}_worker", "synthesize")
    g.add_edge("synthesize", "finalize")
    g.add_edge("finalize", END)
    return g.compile()

_GRAPH = None
def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_multi_agent_graph()
    return _GRAPH
