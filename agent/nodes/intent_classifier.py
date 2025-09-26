from __future__ import annotations

from enum import Enum
from typing import Any, Dict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from ..state import AgentState, merged_context


class IntentLabel(str, Enum):
    GRAPH_MUTATION = "graph_mutation"
    SCENARIO_REQUEST = "scenario_request"
    STATUS_UPDATE = "status_update"
    CYHPER_QUERY = "cypher_query"
    SMALL_TALK = "small_talk"
    UNKNOWN = "unknown"


intent_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "Classify the user's latest message into one intent label."),
        ("user", "Conversation so far: {transcript}\n\nClassify the latest user message."),
    ]
)


async def classify_intent(state: AgentState, llm: BaseChatModel) -> Dict[str, Any]:
    messages = state.get("messages", [])
    human_messages = [m for m in messages if isinstance(m, HumanMessage)]
    if not human_messages:
        return merged_context(state, intent=IntentLabel.UNKNOWN.value, intent_reason="no human message")
    transcript = "\n".join(f"{m.type}: {m.content}" for m in messages[-6:])
    prompt = intent_prompt.invoke({"transcript": transcript})
    structured_llm = llm.with_structured_output(
        schema={
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "enum": [label.value for label in IntentLabel],
                },
                "confidence": {"type": "number"},
                "reason": {"type": "string"},
            },
            "required": ["intent", "confidence"],
        }
    )
    result = await structured_llm.ainvoke(prompt.to_messages())
    return merged_context(
        state,
        intent=result["intent"],
        intent_confidence=result.get("confidence"),
        intent_reason=result.get("reason"),
    )
