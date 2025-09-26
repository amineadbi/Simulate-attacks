from __future__ import annotations

from ..models import ScenarioStatus
from ..state import AgentState
from .intent_classifier import IntentLabel


def route(state: AgentState) -> str:
    active_job = state.get("active_job")
    if active_job and active_job.status in {ScenarioStatus.RUNNING, ScenarioStatus.PENDING}:
        return "monitor_job"

    intent_value = state.get("context", {}).get("intent", IntentLabel.UNKNOWN.value)
    intent = IntentLabel(intent_value) if intent_value in IntentLabel._value2member_map_ else IntentLabel.UNKNOWN

    if intent == IntentLabel.GRAPH_MUTATION:
        return "plan_graph_action"
    if intent == IntentLabel.SCENARIO_REQUEST:
        return "plan_scenario"
    if intent == IntentLabel.STATUS_UPDATE and active_job:
        return "summarise_job"
    if intent == IntentLabel.CYHPER_QUERY:
        return "run_cypher"
    return "respond"
