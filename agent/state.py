from __future__ import annotations

import operator
from typing import Any, Dict, List, Optional, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from .models import GraphMutation, ScenarioJob, ScenarioPlan, ToolCallResult


class AgentState(TypedDict, total=False):
    messages: List[AnyMessage]
    pending_plan: Optional[ScenarioPlan]
    active_job: Optional[ScenarioJob]
    graph_mutations: List[GraphMutation]
    tool_history: List[ToolCallResult]
    context: Dict[str, Any]


AgentStateAnnotations = {
    "messages": add_messages,
    "graph_mutations": operator.add,
    "tool_history": operator.add,
}


def merged_context(state: AgentState, **updates: Any) -> Dict[str, Any]:
    current = dict(state.get("context", {}))
    current.update({k: v for k, v in updates.items() if v is not None})
    return {"context": current}
