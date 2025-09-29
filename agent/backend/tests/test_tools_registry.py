"""
Tests for the tools registry functionality.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from agent.tools import ToolRegistry, MCPToolClient
from agent.config import MCPToolConfig
from agent.mcp_integration import Neo4jMCPClient


class TestMCPToolClient:
    """Test MCP tool client functionality."""

    @pytest.fixture
    def config(self):
        """Create test MCP tool config."""
        return MCPToolConfig(
            name="test-tool",
            base_url="http://localhost:8080",
            api_key="test-key",
            timeout_seconds=30
        )

    @pytest.fixture
    def client(self, config):
        """Create MCP tool client."""
        return MCPToolClient(config)

    def test_client_initialization(self, client, config):
        """Test client initializes with correct configuration."""
        assert client.name == config.name
        assert client._config == config

    @pytest.mark.asyncio
    async def test_client_invoke_success(self, client):
        """Test successful tool invocation."""
        # Mock httpx response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}

        with pytest.mock.patch.object(client._client, 'post', return_value=mock_response):
            result = await client.invoke("test/endpoint", {"param": "value"})

            assert result.name == "test-tool:test/endpoint"
            assert result.response == {"result": "success"}
            assert isinstance(result.elapsed_ms, float)

    @pytest.mark.asyncio
    async def test_client_invoke_with_auth(self, config):
        """Test tool invocation with authentication."""
        config.api_key = "secret-key"
        client = MCPToolClient(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "authenticated"}

        with pytest.mock.patch.object(client._client, 'post', return_value=mock_response) as mock_post:
            await client.invoke("secure/endpoint", {})

            # Verify auth header was included
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            headers = call_args[1]["headers"]
            assert headers["Authorization"] == "Bearer secret-key"

    @pytest.mark.asyncio
    async def test_client_invoke_error(self, client):
        """Test tool invocation error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"

        with pytest.mock.patch.object(client._client, 'post', return_value=mock_response):
            with pytest.raises(Exception) as exc_info:
                await client.invoke("failing/endpoint", {})

            assert "failed with 500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_client_close(self, client):
        """Test client cleanup."""
        with pytest.mock.patch.object(client._client, 'aclose') as mock_close:
            await client.aclose()
            mock_close.assert_called_once()


class TestToolRegistry:
    """Test tool registry functionality."""

    @pytest.fixture
    def mock_configs(self):
        """Create mock tool configurations."""
        return [
            MCPToolConfig(name="tool1", base_url="http://localhost:8081"),
            MCPToolConfig(name="tool2", base_url="http://localhost:8082")
        ]

    @pytest.fixture
    def registry(self, mock_configs):
        """Create tool registry with mock configs."""
        return ToolRegistry.from_config(mock_configs)

    def test_registry_from_config(self, registry, mock_configs):
        """Test registry creation from config."""
        assert len(registry._clients) == 2
        assert "tool1" in registry._clients
        assert "tool2" in registry._clients

    def test_registry_create_minimal(self):
        """Test minimal registry creation."""
        registry = ToolRegistry.create_minimal()
        assert len(registry._clients) == 0
        assert registry._mcp_client is None
        assert registry._mcp_operations is None

    def test_get_client_success(self, registry):
        """Test getting existing client."""
        client = registry.get("tool1")
        assert isinstance(client, MCPToolClient)
        assert client.name == "tool1"

    def test_get_client_not_found(self, registry):
        """Test getting non-existent client."""
        with pytest.raises(KeyError) as exc_info:
            registry.get("nonexistent")

        assert "Tool 'nonexistent' not registered" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_mcp_client(self, registry):
        """Test getting MCP client."""
        with pytest.mock.patch('agent.tools.Neo4jMCPClient') as MockClient:
            mock_instance = AsyncMock()
            MockClient.return_value = mock_instance

            client = await registry.get_mcp_client()

            assert client is mock_instance
            MockClient.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_mcp_client_cached(self, registry):
        """Test MCP client is cached."""
        with pytest.mock.patch('agent.tools.Neo4jMCPClient') as MockClient:
            mock_instance = AsyncMock()
            MockClient.return_value = mock_instance

            # First call
            client1 = await registry.get_mcp_client()
            # Second call
            client2 = await registry.get_mcp_client()

            # Should be the same instance
            assert client1 is client2
            # Constructor should only be called once
            MockClient.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_mcp_operations(self, registry):
        """Test getting MCP operations."""
        mock_client = AsyncMock()

        with pytest.mock.patch.object(registry, 'get_mcp_client', return_value=mock_client):
            with pytest.mock.patch('agent.tools.MCPGraphOperations') as MockOps:
                mock_ops_instance = AsyncMock()
                MockOps.return_value = mock_ops_instance

                ops = await registry.get_mcp_operations()

                assert ops is mock_ops_instance
                MockOps.assert_called_once_with(mock_client)

    @pytest.mark.asyncio
    async def test_get_mcp_operations_cached(self, registry):
        """Test MCP operations are cached."""
        mock_client = AsyncMock()

        with pytest.mock.patch.object(registry, 'get_mcp_client', return_value=mock_client):
            with pytest.mock.patch('agent.tools.MCPGraphOperations') as MockOps:
                mock_ops_instance = AsyncMock()
                MockOps.return_value = mock_ops_instance

                # First call
                ops1 = await registry.get_mcp_operations()
                # Second call
                ops2 = await registry.get_mcp_operations()

                # Should be the same instance
                assert ops1 is ops2
                # Constructor should only be called once
                MockOps.assert_called_once()

    @pytest.mark.asyncio
    async def test_registry_cleanup(self, registry):
        """Test registry cleanup."""
        # Add mock clients
        mock_client1 = AsyncMock()
        mock_client2 = AsyncMock()
        registry._clients = {"tool1": mock_client1, "tool2": mock_client2}
        registry._mcp_client = AsyncMock()

        await registry.aclose()

        # All HTTP clients should be closed
        mock_client1.aclose.assert_called_once()
        mock_client2.aclose.assert_called_once()

        # MCP client and operations should be cleared
        assert registry._mcp_client is None
        assert registry._mcp_operations is None

    @pytest.mark.asyncio
    async def test_registry_cleanup_error_handling(self, registry):
        """Test registry cleanup handles errors gracefully."""
        # Mock client that raises error on close
        mock_client = AsyncMock()
        mock_client.aclose.side_effect = Exception("Close failed")
        registry._clients = {"failing_tool": mock_client}

        # Should not raise exception
        await registry.aclose()

        # Should still clear MCP references
        assert registry._mcp_client is None
        assert registry._mcp_operations is None


class TestToolRegistryIntegration:
    """Integration tests for tool registry with real MCP client."""

    @pytest.fixture
    def minimal_registry(self):
        """Create minimal registry for integration tests."""
        return ToolRegistry.create_minimal()

    @pytest.mark.asyncio
    async def test_mcp_client_integration(self, minimal_registry):
        """Test integration with actual MCP client creation."""
        # This tests the actual creation flow without mocking
        try:
            client = await minimal_registry.get_mcp_client()
            assert isinstance(client, Neo4jMCPClient)

            ops = await minimal_registry.get_mcp_operations()
            assert ops is not None
            assert ops.client is client

        finally:
            # Cleanup
            await minimal_registry.aclose()

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, minimal_registry):
        """Test full lifecycle of registry usage."""
        try:
            # Get MCP client
            client = await minimal_registry.get_mcp_client()
            assert client is not None

            # Get operations
            ops = await minimal_registry.get_mcp_operations()
            assert ops is not None

            # Verify caching works
            client2 = await minimal_registry.get_mcp_client()
            ops2 = await minimal_registry.get_mcp_operations()

            assert client is client2
            assert ops is ops2

        finally:
            # Cleanup should work without errors
            await minimal_registry.aclose()