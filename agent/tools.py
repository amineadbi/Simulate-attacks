from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Iterable, List, Optional

import httpx
from pydantic import BaseModel, Field

from .caldera import CalderaClient, CalderaSettings, CalderaUnavailableError
from .mcp_integration import MCPGraphOperations, Neo4jMCPClient
from .models import ToolCallResult

logger = logging.getLogger(__name__)


class MCPToolConfig(BaseModel):
    """Configuration schema for external MCP HTTP tools."""

    name: str
    base_url: str
    api_key: Optional[str] = None
    timeout_seconds: float = Field(default=30.0, ge=1.0)
    verify_ssl: bool = True


class MCPToolClient:
    """Async HTTP client for an MCP tool exposed over REST."""

    def __init__(self, config: MCPToolConfig):
        self.name = config.name
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            verify=config.verify_ssl,
        )

    async def invoke(self, endpoint: str, payload: Dict[str, Any]) -> ToolCallResult:
        """Invoke a tool endpoint with JSON payload."""
        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"

        url = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        start = time.perf_counter()
        response = await self._client.post(url, json=payload, headers=headers)
        elapsed_ms = (time.perf_counter() - start) * 1000

        if response.status_code >= 400:
            raise RuntimeError(
                f"Tool '{self.name}' endpoint '{endpoint}' failed with {response.status_code}: {response.text}"
            )

        try:
            data = response.json()
        except ValueError as exc:  # pragma: no cover - defensive
            raise RuntimeError(
                f"Tool '{self.name}' endpoint '{endpoint}' returned non-JSON response"
            ) from exc

        return ToolCallResult(
            name=f"{self.name}:{endpoint}",
            request=payload,
            response=data,
            elapsed_ms=elapsed_ms,
        )

    async def aclose(self) -> None:
        await self._client.aclose()


class ToolRegistry:
    """Registry for managing MCP tools, Neo4j operations, and simulation clients."""

    def __init__(
        self,
        configs_or_clients: Optional[Iterable[MCPToolConfig] | Dict[str, MCPToolClient]] = None,
        *,
        caldera_settings: Optional[CalderaSettings] = None,
    ) -> None:
        self._clients: Dict[str, MCPToolClient] = {}
        if isinstance(configs_or_clients, dict):
            self._clients = dict(configs_or_clients)
        elif configs_or_clients:
            for cfg in configs_or_clients:
                self.register(cfg)

        self._caldera_settings = caldera_settings
        self._caldera_client: Optional[CalderaClient] = None
        self._mcp_client: Optional[Neo4jMCPClient] = None
        self._mcp_operations: Optional[MCPGraphOperations] = None
        self._mcp_init_lock = asyncio.Lock()  # Prevent race conditions during initialization

    @classmethod
    def from_config(
        cls,
        configs: Iterable[MCPToolConfig],
        *,
        caldera_settings: Optional[CalderaSettings] = None,
    ) -> "ToolRegistry":
        return cls(configs, caldera_settings=caldera_settings)

    @classmethod
    def create_minimal(
        cls,
        *,
        caldera_settings: Optional[CalderaSettings] = None,
    ) -> "ToolRegistry":
        """Create registry for stdio-based MCP tools with optional Caldera support."""
        return cls(caldera_settings=caldera_settings)

    def register(self, config: MCPToolConfig) -> None:
        if config.name in self._clients:
            raise ValueError(f"Tool '{config.name}' already registered")
        self._clients[config.name] = MCPToolClient(config)
        logger.info("Registered MCP tool '%s'", config.name)

    def get(self, name: str) -> MCPToolClient:
        try:
            return self._clients[name]
        except KeyError as exc:
            raise KeyError(f"Tool '{name}' not registered") from exc

    async def get_caldera_client(self) -> CalderaClient:
        """Get or create the Caldera REST client."""
        if not self._caldera_settings or not self._caldera_settings.enabled:
            raise CalderaUnavailableError("Caldera integration is disabled")
        if not self._caldera_client:
            self._caldera_client = CalderaClient(self._caldera_settings)
            logger.info("Initialized Caldera client")
        return self._caldera_client

    async def get_mcp_client(self) -> Neo4jMCPClient:
        """Get or create the stdio-based MCP client for direct operations with proper async initialization."""
        # Note: Lock is handled by caller (get_mcp_operations) to avoid deadlock
        if not self._mcp_client:
            try:
                client = Neo4jMCPClient()
                # Initialize transport with proper error handling
                await client.__aenter__()
                self._mcp_client = client
                logger.info("Created and initialized new Neo4j MCP client")
            except Exception as e:
                logger.error(f"Failed to initialize MCP client: {e}", exc_info=True)
                raise RuntimeError(f"MCP client initialization failed: {e}") from e
        return self._mcp_client

    async def get_mcp_operations(self) -> MCPGraphOperations:
        """Get or create the MCP graph operations helper with proper async initialization."""
        async with self._mcp_init_lock:
            if not self._mcp_operations:
                try:
                    client = await self.get_mcp_client()
                    self._mcp_operations = MCPGraphOperations(client)
                    logger.info("Created new MCP graph operations")
                except Exception as e:
                    logger.error(f"Failed to create MCP operations: {e}", exc_info=True)
                    raise RuntimeError(f"MCP operations creation failed: {e}") from e
        return self._mcp_operations

    async def aclose(self) -> None:
        """Close all clients and clean up resources."""
        # Close HTTP tool clients
        close_tasks = []
        for name, client in list(self._clients.items()):
            close_tasks.append(self._safe_close_tool(name, client))
        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)
        self._clients.clear()

        # Close MCP client properly
        if self._mcp_client:
            try:
                await self._mcp_client.__aexit__(None, None, None)
                logger.info("MCP client closed")
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Error closing MCP client: %s", exc)

        if self._caldera_client:
            try:
                await self._caldera_client.aclose()
                logger.info("Caldera client closed")
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Error closing Caldera client: %s", exc)

        self._caldera_client = None
        self._mcp_client = None
        self._mcp_operations = None
        logger.info("Tool registry closed")

    async def _safe_close_tool(self, name: str, client: MCPToolClient) -> None:
        close = getattr(client, 'aclose', None) or getattr(client, 'close', None)
        if not close:
            return
        try:
            result = close()
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error closing tool '%s': %s", name, exc)


__all__ = [
    "MCPToolConfig",
    "MCPToolClient",
    "ToolRegistry",
]
