from typing import Annotated, Any, TypedDict
import operator


class AgentState(TypedDict, total=False):
    session_id: str
    task: str
    system: str
    tools: list[dict]
    max_iter: int
    iteration: int
    input_items: list[dict]
    tool_call_log: Annotated[list[dict], operator.add]
    llm_output: Any
    final_text: str
    error: str
