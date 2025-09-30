from __future__ import annotations

from typing import Any, Dict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate

from ..state import AgentState
from ..tools import ToolRegistry

PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "Draft a safe Cypher query for the network defence graph."),
        (
            "user",
            "Conversation snippet:\n{transcript}\n\nReturn JSON with query, params, mode (read|write), and a short justification.",
        ),
    ]
)

SCHEMA = {
    "title": "CypherQueryPlan",
    "description": "Plan for executing a Cypher query on the graph database",
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "params": {"type": "object"},
        "mode": {"type": "string", "enum": ["read", "write"]},
        "justification": {"type": "string"},
        "limit": {"type": "integer", "minimum": 1},
    },
    "required": ["query", "mode"],
}


async def run_cypher(state: AgentState, llm: BaseChatModel, tools: ToolRegistry) -> Dict[str, Any]:
    messages = state.get("messages", [])
    transcript = "\n".join(f"{m.type}: {m.content}" for m in messages[-6:])
    structured_llm = llm.with_structured_output(schema=SCHEMA)
    plan = await structured_llm.ainvoke(PROMPT.invoke({"transcript": transcript}).to_messages())
    query = plan["query"]
    params = plan.get("params", {})
    mode = plan["mode"]
    limit = plan.get("limit")
    payload: Dict[str, Any] = {"query": query, "params": params, "mode": mode}
    if limit:
        payload["limit"] = limit

    client = tools.get("graph")
    result = await client.invoke("run_cypher", payload)
    records = result.response.get("records", [])
    message = AIMessage(
        content=(
            f"Ran Cypher in {mode} mode. Returned {len(records)} rows. "
            f"Justification: {plan.get('justification', 'n/a')}"
        )
    )
    return {"tool_history": [result], "messages": [message]}
