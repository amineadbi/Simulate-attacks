from __future__ import annotations

import logging
from typing import Optional

from .mcp_integration import Neo4jMCPClient, MCPGraphOperations

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for managing MCP tools and Neo4j operations."""

    def __init__(self):
        self._mcp_client: Optional[Neo4jMCPClient] = None
        self._mcp_operations: Optional[MCPGraphOperations] = None

    @classmethod
    def create_minimal(cls) -> "ToolRegistry":
        """Create registry for stdio-based MCP tools."""
        return cls()

    async def get_mcp_client(self) -> Neo4jMCPClient:
        """Get or create the stdio-based MCP client for direct operations."""
        if not self._mcp_client:
            self._mcp_client = Neo4jMCPClient()
            # Initialize the client immediately
            await self._mcp_client.__aenter__()
            logger.info("Created and initialized new Neo4j MCP client")
        return self._mcp_client

    async def get_mcp_operations(self) -> MCPGraphOperations:
        """Get or create the MCP graph operations helper."""
        if not self._mcp_operations:
            client = await self.get_mcp_client()
            self._mcp_operations = MCPGraphOperations(client)
            logger.info("Created new MCP graph operations")
        return self._mcp_operations

    async def aclose(self) -> None:
        """Close all clients and clean up resources."""
        # Close MCP client properly
        if self._mcp_client:
            try:
                await self._mcp_client.__aexit__(None, None, None)
                logger.info("MCP client closed")
            except Exception as e:
                logger.warning(f"Error closing MCP client: {e}")

        self._mcp_client = None
        self._mcp_operations = None
        logger.info("Tool registry closed")
