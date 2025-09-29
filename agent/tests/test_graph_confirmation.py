import pytest

from agent.models import GraphActionPlan, GraphMutation, MutationType, ToolCallResult
from agent.nodes import graph_tools
from agent.tools import ToolRegistry


class DummyClient:
    def __init__(self):
        self.calls = []

    async def invoke(self, path: str, payload: dict):
        self.calls.append((path, payload))
        return ToolCallResult(name=f"graph:{path}", request=payload, response={"status": "ok"})


def _make_plan(require_confirmation: bool = True) -> GraphActionPlan:
    mutation = GraphMutation(entity="node", target_id="n1", mutation=MutationType.DELETE, payload={})
    return GraphActionPlan(
        tool_name="graph::delete_node",
        arguments={"id": "n1"},
        reasoning="cleanup",
        mutation=mutation,
        requires_confirmation=require_confirmation,
    )


def _make_state(plan: GraphActionPlan) -> dict:
    return {
        "context": {
            "graph_plan": plan.model_dump(mode="json"),
            "graph_plan_confirmed": False,
        }
    }


@pytest.mark.asyncio
async def test_execute_requires_confirmation_before_invoking():
    plan = _make_plan(require_confirmation=True)
    state = _make_state(plan)
    dummy = DummyClient()
    registry = ToolRegistry({"graph": dummy})

    result = await graph_tools.execute_graph_action(state, registry)

    assert dummy.calls == []
    assert result["messages"][0].content.lower().startswith("planned operation is destructive")


@pytest.mark.asyncio
async def test_confirmation_enables_execution():
    plan = _make_plan(require_confirmation=True)
    state = _make_state(plan)
    dummy = DummyClient()
    registry = ToolRegistry({"graph": dummy})

    confirm_update = await graph_tools.confirm_graph_action(state)
    state["context"] = confirm_update["context"]

    result = await graph_tools.execute_graph_action(state, registry)

    assert len(dummy.calls) == 1
    assert dummy.calls[0][0] == "delete_node"
    assert result["context"]["graph_plan"] is None
    assert result["context"]["graph_plan_confirmed"] is False


@pytest.mark.asyncio
async def test_rejection_clears_plan():
    plan = _make_plan(require_confirmation=True)
    state = _make_state(plan)

    result = await graph_tools.reject_graph_action(state)

    assert result["context"]["graph_plan"] is None
    assert result["context"]["graph_plan_confirmed"] is False
    assert "Cancelled" in result["messages"][0].content
