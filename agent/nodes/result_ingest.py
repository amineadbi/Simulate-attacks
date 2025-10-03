from __future__ import annotations

from typing import Any, Dict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate

from ..models import ScenarioStatus
from ..state import AgentState
from ..tools import ToolRegistry

SUMMARY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Summarise breach-and-attack simulation findings for a security operations audience.",
        ),
        (
            "user",
            "Job context: {job_context}\nFindings JSON: {findings}",
        ),
    ]
)


async def summarise_job(state: AgentState, llm: BaseChatModel, tools: ToolRegistry) -> Dict[str, Any]:
    context = state.get("context", {})
    job_id = context.get("last_job_id")
    platform = context.get("last_job_platform")
    status = context.get("last_job_status")
    if not job_id or not platform:
        return {"messages": [AIMessage(content="No job information available.")]}

    # Note: Result fetching for simulation platforms is not yet implemented
    # This would require additional platform-specific clients (Caldera, Metasploit, etc.)
    findings = {"job_id": job_id, "platform": platform, "status": status, "note": "Result fetching not yet implemented"}

    summary = await llm.ainvoke(
        SUMMARY_PROMPT.format_messages(
            job_context=f"job_id={job_id}, platform={platform}, status={status}", findings=findings
        )
    )
    return {
        "messages": [AIMessage(content=summary.content)],
    }
