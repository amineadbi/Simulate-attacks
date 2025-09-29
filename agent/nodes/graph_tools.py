from __future__ import annotations

from typing import Any, Dict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate

from ..models import GraphActionPlan, GraphMutation, MutationType
from ..state import AgentState, merged_context
from ..tools import ToolRegistry

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "tool_name": {"type": "string"},
        "arguments": {"type": "object"},
        "reasoning": {"type": "string"},
        "requires_confirmation": {"type": "boolean"},
        "entity": {"type": "string"},
        "target_id": {"type": "string"},
        "mutation": {"type": "string", "enum": [m.value for m in MutationType]},
        "payload": {"type": "object"},
    },
    "required": ["tool_name", "arguments", "reasoning", "entity", "target_id", "mutation"],
}

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You translate user requests into precise graph tool calls for a network defence assistant.",
        ),
        (
            "user",
            "Conversation window:\n{transcript}\n\nProduce the next graph operation in JSON only.",
        ),
    ]
)


def _build_plan(raw: Dict[str, Any]) -> GraphActionPlan:
    mutation = GraphMutation(
        entity=raw["entity"],
        target_id=raw["target_id"],
        mutation=MutationType(raw["mutation"]),
        payload=raw.get("payload", {}),
    )
    return GraphActionPlan(
        tool_name=raw["tool_name"],
        arguments=raw.get("arguments", {}),
        reasoning=raw.get("reasoning", ""),
        mutation=mutation,
        requires_confirmation=raw.get("requires_confirmation", False),
    )


def _split_tool_name(reference: str) -> tuple[str, str]:
    for separator in ("::", "/", ":"):
        if separator in reference:
            left, right = reference.split(separator, 1)
            return left, right
    raise ValueError(f"Invalid tool reference '{reference}'. Expect format 'client::path'.")


async def confirm_graph_action(state: AgentState) -> Dict[str, Any]:
    plan_data = state.get("context", {}).get("graph_plan")
    if not plan_data:
        return {"messages": [AIMessage(content="No pending graph operation to confirm.")]}
    plan = GraphActionPlan.model_validate(plan_data)
    ctx_update = merged_context(state, graph_plan_confirmed=True)
    message = AIMessage(
        content=(
            f"Confirmed {plan.mutation.mutation.value} {plan.mutation.entity} {plan.mutation.target_id}."
        )
    )
    return {**ctx_update, "messages": [message]}


async def reject_graph_action(state: AgentState) -> Dict[str, Any]:
    plan_data = state.get("context", {}).get("graph_plan")
    if not plan_data:
        return {"messages": [AIMessage(content="No pending graph operation to cancel.")]}
    plan = GraphActionPlan.model_validate(plan_data)
    ctx_update = merged_context(state, graph_plan=None, graph_plan_confirmed=False)
    message = AIMessage(
        content=(
            f"Cancelled {plan.mutation.mutation.value} {plan.mutation.entity} {plan.mutation.target_id}. No changes applied."
        )
    )
    return {**ctx_update, "messages": [message]}


async def plan_graph_action(state: AgentState, llm: BaseChatModel) -> Dict[str, Any]:
    messages = state.get("messages", [])
    transcript = "\n".join(f"{m.type}: {m.content}" for m in messages[-6:])
    chat_input = prompt.invoke({"transcript": transcript})
    structured_llm = llm.with_structured_output(schema=PLAN_SCHEMA)
    raw_plan = await structured_llm.ainvoke(chat_input.to_messages())
    plan = _build_plan(raw_plan)
    summary = (
        f"Planning to call {plan.tool_name} targeting {plan.mutation.target_id} "
        f"({plan.mutation.mutation.value})."
    )
    ctx_update = merged_context(
        state,
        graph_plan=plan.model_dump(mode="json"),
        graph_plan_confirmed=False,
    )
    return {
        **ctx_update,
        "graph_mutations": [plan.mutation],
        "messages": [AIMessage(content=summary)],
    }


async def execute_graph_action(state: AgentState, tools: ToolRegistry) -> Dict[str, Any]:
    plan_data = state.get("context", {}).get("graph_plan")
    if not plan_data:
        return {}
    plan = GraphActionPlan.model_validate(plan_data)

    if plan.requires_confirmation and not state.get("context", {}).get("graph_plan_confirmed"):
        message = AIMessage(
            content=(
                "Planned operation is destructive. Please confirm before execution: "
                f"{plan.mutation.mutation.value} {plan.mutation.entity} {plan.mutation.target_id}."
            )
        )
        return {"messages": [message]}

    # Get the MCP client and operations
    mcp_client = await tools.get_mcp_client()
    mcp_ops = await tools.get_mcp_operations()

    # Execute operation via MCP
    mutation = plan.mutation
    try:
        async with mcp_client:
            if mutation.mutation == MutationType.CREATE:
                if mutation.entity == "node":
                    result = await mcp_ops.add_node(mutation.payload)
                elif mutation.entity == "edge":
                    result = await mcp_ops.add_edge(mutation.payload)
                else:
                    raise ValueError(f"Unknown entity type: {mutation.entity}")
            elif mutation.mutation == MutationType.UPDATE:
                if mutation.entity == "node":
                    result = await mcp_ops.update_node(mutation.target_id, mutation.payload)
                elif mutation.entity == "edge":
                    result = await mcp_ops.update_edge(mutation.target_id, mutation.payload)
                else:
                    raise ValueError(f"Unknown entity type: {mutation.entity}")
            elif mutation.mutation == MutationType.DELETE:
                if mutation.entity == "node":
                    result = await mcp_ops.delete_node(mutation.target_id)
                elif mutation.entity == "edge":
                    result = await mcp_ops.delete_edge(mutation.target_id)
                else:
                    raise ValueError(f"Unknown entity type: {mutation.entity}")
            else:
                raise ValueError(f"Unknown mutation type: {mutation.mutation}")

        message = AIMessage(
            content=(
                f"Executed {mutation.mutation.value} {mutation.entity} {mutation.target_id} via MCP. "
                f"Status: {result.get('status', 'completed')}"
            )
        )
        ctx_update = merged_context(state, graph_plan=None, graph_plan_confirmed=False)
        return {
            **ctx_update,
            "tool_history": [{"name": "mcp_graph_operation", "result": result}],
            "messages": [message],
        }

    except Exception as e:
        message = AIMessage(
            content=f"Failed to execute graph operation: {str(e)}"
        )
        return {"messages": [message]}
