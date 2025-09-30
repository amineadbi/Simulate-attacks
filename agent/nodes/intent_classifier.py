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
    CYPHER_QUERY = "cypher_query"
    CONFIRMATION = "confirmation"
    REJECTION = "rejection"
    SMALL_TALK = "small_talk"
    UNKNOWN = "unknown"


intent_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Classify the user's latest message into exactly one intent label based on their request:

**Intent Labels & Criteria:**
- **graph_mutation**: User wants to add, modify, or delete nodes/edges in the graph (e.g., "add a server", "remove this connection", "update node properties")
- **scenario_request**: User wants to start a breach/attack simulation (e.g., "run a phishing simulation", "test lateral movement", "simulate ransomware attack")
- **status_update**: User asks about current scenario/job status (e.g., "how is the attack going?", "what's the status?", "is it finished?")
- **cypher_query**: User wants to query the graph database directly (e.g., "show all servers", "find nodes with label X", "run this query")
- **confirmation**: User explicitly approves a pending action with clear affirmative language (e.g., "yes", "proceed", "do it", "confirmed")
- **rejection**: User explicitly declines or cancels a pending action (e.g., "no", "cancel", "stop", "don't do that")
- **small_talk**: Greetings, casual conversation, or general questions not related to security analysis
- **unknown**: Ambiguous requests that don't clearly fit other categories

**Context Considerations:**
- Look at the conversation history to understand if there's a pending action awaiting confirmation
- Consider security-specific terminology and context
- Distinguish between asking for information vs. requesting actions""",
        ),
        ("user", "Recent conversation:\n{transcript}\n\nClassify the LATEST user message's intent:"),
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
            "title": "IntentClassification",
            "description": "Classification of user intent from their message",
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
