from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from langchain_core.messages import AIMessage, HumanMessage

from agent.flow import AgentApplication, create_application
from agent.models import GraphMutation, ToolCallResult
from agent.state import AgentState

from .events import AgentEvent, Connection, EventBroker
from .graph_service import GraphService
from .serializers import serialize_job


class AgentSession:
    def __init__(self, *, connection: Connection, broker: EventBroker, graph_service: GraphService) -> None:
        self._connection = connection
        self._broker = broker
        self._graph_service = graph_service
        self._application: AgentApplication = create_application()
        self._state: AgentState = {}
        self._message_count = 0
        self._tool_count = 0
        self._mutation_count = 0
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        await self._send_event("notification", {"message": "session-ready"})

    async def aclose(self) -> None:
        await self._application.aclose()

    async def handle_message(self, payload: Dict[str, Any]) -> None:
        message_type = payload.get("type")
        if message_type == "graph.request":
            await self._handle_graph_request(payload)
            return
        if message_type == "agent.command":
            await self._handle_agent_command(payload)
            return
        if message_type == "scenario.run":
            await self._handle_scenario_hint(payload)
            return
        await self._send_event(
            "agent.log",
            {"message": f"Unsupported message type '{message_type}'"},
            level="warn",
        )

    async def _handle_graph_request(self, payload: Dict[str, Any]) -> None:
        graph = self._graph_service.export_graph()
        await self._send_event("graph.replace", graph.model_dump(mode="json"))

    async def _handle_scenario_hint(self, payload: Dict[str, Any]) -> None:
        # Scenario execution is primarily handled through REST; we simply acknowledge the hint here.
        scenario_id = payload.get("scenarioId")
        await self._send_event(
            "agent.log",
            {"message": f"Scenario hint received for {scenario_id}"},
            level="debug",
        )

    async def _handle_agent_command(self, payload: Dict[str, Any]) -> None:
        command = payload.get("command")
        body = payload.get("payload") or {}
        if command != "chat":
            await self._send_event(
                "agent.log",
                {"message": f"Unsupported command '{command}'"},
                level="warn",
            )
            return
        text = (body.get("text") or "").strip()
        if not text:
            await self._send_event("agent.log", {"message": "Empty message"}, level="warn")
            return

        async with self._lock:
            await self._send_event(
                "agent.message",
                {"role": "user", "content": text},
                level="info",
            )
            self._state.setdefault("messages", []).append(HumanMessage(content=text))
            try:
                next_state = await self._application.graph.ainvoke(self._state)
            except Exception as exc:  # pragma: no cover - safety
                await self._send_event(
                    "agent.log",
                    {"message": f"Agent run failed: {exc}"},
                    level="error",
                )
                return
            self._state = next_state
            await self._emit_new_messages()
            await self._emit_tool_updates()
            await self._emit_graph_mutations()
            await self._emit_active_job()

    async def _emit_new_messages(self) -> None:
        messages = self._state.get("messages", [])
        for message in messages[self._message_count :]:
            if isinstance(message, AIMessage):
                await self._send_event(
                    "agent.message",
                    {"role": "assistant", "content": message.content},
                    level="info",
                )
        self._message_count = len(messages)

    async def _emit_tool_updates(self) -> None:
        history = self._state.get("tool_history", [])
        for entry in history[self._tool_count :]:
            if isinstance(entry, ToolCallResult):
                await self._send_event(
                    "agent.step",
                    {
                        "name": entry.name,
                        "request": entry.request,
                        "response": entry.response,
                        "elapsedMs": entry.elapsed_ms,
                        "error": entry.error,
                    },
                    level="debug" if not entry.error else "error",
                )
        self._tool_count = len(history)

    async def _emit_graph_mutations(self) -> None:
        mutations = self._state.get("graph_mutations", [])
        new_mutations = [m for m in mutations[self._mutation_count :] if isinstance(m, GraphMutation)]
        if not new_mutations:
            self._mutation_count = len(mutations)
            return
        highlight_ids = [mutation.target_id for mutation in new_mutations if mutation.target_id]
        if highlight_ids:
            await self._send_event("graph.highlight", {"nodeIds": highlight_ids})
        self._mutation_count = len(mutations)

    async def _emit_active_job(self) -> None:
        job = self._state.get("active_job")
        if not job:
            return
        try:
            payload = job.model_dump(mode="json")
        except AttributeError:  # pragma: no cover - safety
            payload = job
        await self._broker.emit("scenario.status", payload)

    async def _send_event(self, event_type: str, payload: Any, *, level: Optional[str] = None) -> None:
        await self._connection.send(AgentEvent(type=event_type, payload=payload, level=level))


