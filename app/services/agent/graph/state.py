import operator
from typing import Annotated, TypedDict


class AgentState(TypedDict, total=False):
    session_id: str
    task: str
    system: str
    max_iter: int
    requested_tool_set: str
    tool_call_log: Annotated[list[dict], operator.add]
    final_text: str
    workers_selected: list[str]
    result: dict
