from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from .models import GraphMutation, ScenarioJob, ScenarioPlan, ToolCallResult


def merge_context(left: Optional[Dict[str, Any]], right: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Custom reducer for context dict - merge new values into existing."""
    if left is None:
        return right or {}
    if right is None:
        return left
    result = dict(left)
    result.update(right)
    return result


class AgentState(TypedDict, total=False):
    """Agent state with proper LangGraph reducers using Annotated types."""
    messages: Annotated[List[AnyMessage], add_messages]
    pending_plan: Optional[ScenarioPlan]
    active_job: Optional[ScenarioJob]
    graph_mutations: Annotated[List[GraphMutation], operator.add]
    tool_history: Annotated[List[ToolCallResult], operator.add]
    context: Annotated[Dict[str, Any], merge_context]


# Keep annotations dict for backwards compatibility but it's no longer needed
AgentStateAnnotations = {
    "messages": add_messages,
    "graph_mutations": operator.add,
    "tool_history": operator.add,
    "context": merge_context,
}


def merged_context(state: AgentState, **updates: Any) -> Dict[str, Any]:
    current = dict(state.get("context", {}))
    current.update({k: v for k, v in updates.items() if v is not None})
    return {"context": current}
