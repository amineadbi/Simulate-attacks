from __future__ import annotations

from ..models import ScenarioStatus
from ..state import AgentState
from .intent_classifier import IntentLabel


def route(state: AgentState) -> str:
    # Check for active jobs first - highest priority
    active_job = state.get("active_job")
    if active_job and active_job.status in {ScenarioStatus.RUNNING, ScenarioStatus.PENDING}:
        return "monitor_job"

    # Get intent from context with safe fallback
    context = state.get("context", {})
    intent_value = context.get("intent", IntentLabel.UNKNOWN.value)

    # Safe intent parsing
    try:
        intent = IntentLabel(intent_value) if intent_value in IntentLabel._value2member_map_ else IntentLabel.UNKNOWN
    except (ValueError, AttributeError):
        intent = IntentLabel.UNKNOWN

    # Route based on intent with confirmation/rejection checking pending actions
    if intent == IntentLabel.CONFIRMATION:
        if context.get("graph_plan"):
            return "confirm_graph_action"
        # If no pending action to confirm, treat as general response
        return "respond"

    if intent == IntentLabel.REJECTION:
        if context.get("graph_plan"):
            return "reject_graph_action"
        # If no pending action to reject, treat as general response
        return "respond"

    # Standard intent routing
    if intent == IntentLabel.GRAPH_MUTATION:
        return "plan_graph_action"
    if intent == IntentLabel.SCENARIO_REQUEST:
        return "plan_scenario"
    if intent == IntentLabel.STATUS_UPDATE:
        # Only route to summarise_job if there's actually a job to summarize
        if active_job:
            return "summarise_job"
        return "respond"
    if intent == IntentLabel.CYPHER_QUERY:
        return "run_cypher"

    # Default fallback
    return "respond"
