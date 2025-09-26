from __future__ import annotations

from typing import Any, Dict, List

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate

from ..models import ToolCallResult
from ..state import AgentState

PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are Sentinel Guide, a security analyst agent. Reply clearly, cite tool outputs when relevant.",
        ),
        (
            "user",
            "Conversation:\n{transcript}\n\nLatest tool notes:\n{tool_notes}\n\nRespond to the user succinctly and propose next actions.",
        ),
    ]
)


def _format_tools(history: List[ToolCallResult]) -> str:
    if not history:
        return "(no tool invocations)"
    lines = []
    for result in history[-3:]:
        response = result.response
        if isinstance(response, dict):
            keys = ", ".join(response.keys())
        else:
            keys = "ok"
        lines.append(f"- {result.name} -> {keys}")
    return "\n".join(lines)


async def respond(state: AgentState, llm: BaseChatModel) -> Dict[str, Any]:
    messages = state.get("messages", [])
    transcript = "\n".join(f"{m.type}: {m.content}" for m in messages[-6:])
    history = state.get("tool_history", [])
    tool_notes = _format_tools(history)
    reply = await llm.ainvoke(PROMPT.invoke({"transcript": transcript, "tool_notes": tool_notes}).to_messages())
    return {"messages": [reply]}
