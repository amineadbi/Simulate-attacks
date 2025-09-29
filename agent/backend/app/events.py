from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Optional, Set

from fastapi import WebSocket
from pydantic import BaseModel, Field


class AgentEvent(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    type: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="createdAt")
    payload: Any = Field(default_factory=dict)
    level: Optional[str] = None
    source: Optional[str] = None

    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda dt: dt.isoformat()}

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


class Connection:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.id = uuid.uuid4().hex

    def __hash__(self) -> int:  # pragma: no cover - trivial
        return hash(self.id)

    def __eq__(self, other: object) -> bool:  # pragma: no cover - trivial
        if not isinstance(other, Connection):
            return False
        return self.id == other.id

    async def send(self, event: AgentEvent | dict[str, Any]) -> None:
        payload = event.as_dict() if isinstance(event, AgentEvent) else event
        await self.websocket.send_json(payload)


class EventBroker:
    def __init__(self) -> None:
        self._connections: Set[Connection] = set()
        self._lock = asyncio.Lock()

    async def register(self, websocket: WebSocket) -> Connection:
        # WebSocket is already accepted in the endpoint handler
        connection = Connection(websocket)
        async with self._lock:
            self._connections.add(connection)
        return connection

    async def unregister(self, connection: Connection) -> None:
        async with self._lock:
            self._connections.discard(connection)

    async def broadcast(self, event: AgentEvent | dict[str, Any]) -> None:
        payload = event if isinstance(event, dict) else event.as_dict()
        async with self._lock:
            connections: Iterable[Connection] = list(self._connections)
        for connection in connections:
            try:
                await connection.send(payload)
            except Exception:
                await self.unregister(connection)

    async def emit(self, event_type: str, payload: Any, *, level: Optional[str] = None, source: Optional[str] = None) -> None:
        await self.broadcast(AgentEvent(type=event_type, payload=payload, level=level, source=source))


_broker: Optional[EventBroker] = None


def get_broker() -> EventBroker:
    global _broker
    if _broker is None:
        _broker = EventBroker()
    return _broker
