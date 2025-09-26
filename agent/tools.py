from __future__ import annotations

import time
from typing import Any, Dict, Iterable, Mapping, Optional

import httpx

from .config import MCPToolConfig
from .models import ToolCallResult


class MCPError(RuntimeError):
    pass


class MCPToolClient:
    def __init__(self, config: MCPToolConfig):
        self._config = config
        self._client = httpx.AsyncClient(timeout=config.timeout_seconds)

    @property
    def name(self) -> str:
        return self._config.name

    async def invoke(self, path: str, payload: Dict[str, Any]) -> ToolCallResult:
        url = f"{self._config.base_url.rstrip('/')}/{path.lstrip('/')}"
        headers = {}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        start = time.perf_counter()
        response = await self._client.post(url, json=payload, headers=headers)
        elapsed = (time.perf_counter() - start) * 1000
        if response.status_code >= 400:
            raise MCPError(f"{self.name}::{path} failed with {response.status_code}: {response.text}")
        data = response.json()
        return ToolCallResult(name=f"{self.name}:{path}", request=payload, response=data, elapsed_ms=elapsed)

    async def aclose(self) -> None:
        await self._client.aclose()


class ToolRegistry:
    def __init__(self, clients: Mapping[str, MCPToolClient]):
        self._clients = dict(clients)

    @classmethod
    def from_config(cls, configs: Iterable[MCPToolConfig]) -> "ToolRegistry":
        clients = {config.name: MCPToolClient(config) for config in configs}
        return cls(clients)

    def get(self, name: str) -> MCPToolClient:
        if name not in self._clients:
            raise KeyError(f"Tool '{name}' not registered")
        return self._clients[name]

    async def aclose(self) -> None:
        for client in self._clients.values():
            await client.aclose()
