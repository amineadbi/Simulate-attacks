from __future__ import annotations

from typing import Any, Dict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate

from ..models import ScenarioJob, ScenarioPlan, ScenarioStatus
from ..state import AgentState, merged_context
from ..tools import ToolRegistry

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "platform": {"type": "string"},
        "scenario_id": {"type": "string"},
        "objective": {"type": "string"},
        "target_selector": {"type": "object"},
        "parameters": {"type": "object"},
    },
    "required": ["platform", "scenario_id", "objective"],
}

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Design a breach-and-attack simulation run given the user's request and the current graph context.",
        ),
        (
            "user",
            "Recent conversation snippet:\n{transcript}\n\nReturn JSON only.",
        ),
    ]
)


def _build_plan(raw: Dict[str, Any]) -> ScenarioPlan:
    return ScenarioPlan(
        platform=raw["platform"],
        scenario_id=raw["scenario_id"],
        objective=raw["objective"],
        target_selector=raw.get("target_selector", {}),
        parameters=raw.get("parameters", {}),
    )


async def plan_scenario(state: AgentState, llm: BaseChatModel) -> Dict[str, Any]:
    messages = state.get("messages", [])
    transcript = "\n".join(f"{m.type}: {m.content}" for m in messages[-6:])
    structured_llm = llm.with_structured_output(schema=PLAN_SCHEMA)
    raw_plan = await structured_llm.ainvoke(prompt.invoke({"transcript": transcript}).to_messages())
    plan = _build_plan(raw_plan)
    message = AIMessage(
        content=(
            f"Prepared scenario {plan.scenario_id} on platform {plan.platform} with objective: {plan.objective}."
        )
    )
    return {"pending_plan": plan, "messages": [message]}


async def execute_scenario(state: AgentState, tools: ToolRegistry) -> Dict[str, Any]:
    plan = state.get("pending_plan")
    if not plan:
        return {}

    client = tools.get(plan.platform)
    payload = {
        "scenario_id": plan.scenario_id,
        "objective": plan.objective,
        "target_selector": plan.target_selector,
        "parameters": plan.parameters,
    }
    result = await client.invoke("start_attack", payload)
    job_id = result.response.get("job_id", "unknown")
    job = ScenarioJob(job_id=job_id, plan=plan, status=ScenarioStatus.PENDING)
    message = AIMessage(content=f"Scenario queued as job {job_id} on {plan.platform}.")
    ctx_update = merged_context(state, last_job_id=job_id, last_job_platform=plan.platform)
    return {
        **ctx_update,
        "active_job": job,
        "pending_plan": None,
        "tool_history": [result],
        "messages": [message],
    }


async def monitor_job(state: AgentState, tools: ToolRegistry) -> Dict[str, Any]:
    job = state.get("active_job")
    if not job:
        return {}
    client = tools.get(job.plan.platform)
    result = await client.invoke("check_attack", {"job_id": job.job_id})
    status_value = result.response.get("status", job.status.value)
    try:
        status = ScenarioStatus(status_value)
    except ValueError:
        status = job.status
    updated = job.model_copy(update={"status": status})
    message = AIMessage(content=f"Job {job.job_id} status: {status.value}.")
    context_updates = {
        "last_job_id": job.job_id,
        "last_job_platform": job.plan.platform,
        "last_job_status": status.value,
    }
    if status in {ScenarioStatus.SUCCEEDED, ScenarioStatus.FAILED, ScenarioStatus.CANCELLED}:
        context_updates["last_job_final_status"] = status.value
    ctx_update = merged_context(state, **context_updates)
    payload: Dict[str, Any] = {
        **ctx_update,
        "active_job": updated,
        "tool_history": [result],
        "messages": [message],
    }
    if status in {ScenarioStatus.SUCCEEDED, ScenarioStatus.FAILED, ScenarioStatus.CANCELLED}:
        payload["active_job"] = None
    return payload
