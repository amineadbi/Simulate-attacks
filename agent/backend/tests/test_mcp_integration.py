"""
Tests for MCP integration functionality.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.mcp_integration import Neo4jMCPClient, MCPGraphOperations
from agent.backend.app.error_handling import GraphOperationError


class TestNeo4jMCPClient:
    """Test Neo4j MCP client functionality."""

    @pytest.fixture
    def mock_toolkit(self):
        """Create mock MCPToolkit."""
        mock = AsyncMock()
        mock.aget_tools.return_value = [
            MagicMock(name="run-cypher"),
            MagicMock(name="get-schema")
        ]
        return mock

    @pytest.fixture
    def client(self):
        """Create MCP client for testing."""
        return Neo4jMCPClient()

    @pytest.mark.asyncio
    async def test_client_initialization(self, client, mock_toolkit):
        """Test client initializes properly."""
        with patch("agent.mcp_integration.MCPToolkit", return_value=mock_toolkit):
            async with client:
                assert client._initialized is True
                assert client._toolkit is not None

    @pytest.mark.asyncio
    async def test_client_cleanup(self, client, mock_toolkit):
        """Test client cleans up resources."""
        with patch("agent.mcp_integration.MCPToolkit", return_value=mock_toolkit):
            async with client:
                pass
            # After context manager exits
            assert client._toolkit is None
            assert client._initialized is False
            mock_toolkit.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_tool_success(self, client, mock_toolkit):
        """Test successful tool call."""
        mock_tool = AsyncMock()
        mock_tool.name = "run-cypher"
        mock_tool.ainvoke.return_value = {"records": [], "summary": {}}
        mock_toolkit.aget_tools.return_value = [mock_tool]

        with patch("agent.mcp_integration.MCPToolkit", return_value=mock_toolkit):
            async with client:
                result = await client.call_tool("run-cypher", {"query": "MATCH (n) RETURN n"})

                assert "records" in result
                mock_tool.ainvoke.assert_called_once_with({"query": "MATCH (n) RETURN n"})

    @pytest.mark.asyncio
    async def test_call_tool_not_found(self, client, mock_toolkit):
        """Test calling non-existent tool."""
        mock_toolkit.aget_tools.return_value = []

        with patch("agent.mcp_integration.MCPToolkit", return_value=mock_toolkit):
            async with client:
                with pytest.raises(ValueError, match="Tool 'nonexistent' not found"):
                    await client.call_tool("nonexistent", {})

    @pytest.mark.asyncio
    async def test_call_tool_not_initialized(self, client):
        """Test calling tool on uninitialized client."""
        with pytest.raises(RuntimeError, match="MCP client not initialized"):
            await client.call_tool("test", {})

    @pytest.mark.asyncio
    async def test_get_available_tools(self, client, mock_toolkit):
        """Test getting available tools."""
        mock_tools = [
            MagicMock(name="run-cypher"),
            MagicMock(name="get-schema")
        ]
        mock_toolkit.aget_tools.return_value = mock_tools

        with patch("agent.mcp_integration.MCPToolkit", return_value=mock_toolkit):
            async with client:
                tools = await client.get_available_tools()
                assert "run-cypher" in tools
                assert "get-schema" in tools


class TestMCPGraphOperations:
    """Test graph operations functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create mock MCP client."""
        client = AsyncMock(spec=Neo4jMCPClient)
        return client

    @pytest.fixture
    def graph_ops(self, mock_client):
        """Create graph operations instance."""
        return MCPGraphOperations(mock_client)

    @pytest.mark.asyncio
    async def test_get_schema(self, graph_ops, mock_client):
        """Test getting schema."""
        expected_schema = {"nodes": ["Host", "Server"], "relationships": ["CONNECTED"]}
        mock_client.call_tool.return_value = expected_schema

        result = await graph_ops.get_schema()

        assert result == expected_schema
        mock_client.call_tool.assert_called_once_with("get-schema", {})

    @pytest.mark.asyncio
    async def test_run_cypher_success(self, graph_ops, mock_client):
        """Test successful Cypher query execution."""
        expected_result = {"records": [{"n": {"id": "node1"}}], "summary": {"nodes": 1}}
        mock_client.call_tool.return_value = expected_result

        result = await graph_ops.run_cypher("MATCH (n) RETURN n")

        assert result == expected_result
        mock_client.call_tool.assert_called_once_with(
            "run-cypher",
            {"query": "MATCH (n) RETURN n", "params": {}, "mode": "read"}
        )

    @pytest.mark.asyncio
    async def test_run_cypher_with_params(self, graph_ops, mock_client):
        """Test Cypher query with parameters."""
        mock_client.call_tool.return_value = {"records": [], "summary": {}}

        await graph_ops.run_cypher(
            "MATCH (n {id: $id}) RETURN n",
            params={"id": "node1"},
            mode="write"
        )

        mock_client.call_tool.assert_called_once_with(
            "run-cypher",
            {"query": "MATCH (n {id: $id}) RETURN n", "params": {"id": "node1"}, "mode": "write"}
        )

    @pytest.mark.asyncio
    async def test_run_cypher_validation(self, graph_ops):
        """Test Cypher query validation."""
        # Test empty query
        with pytest.raises(ValueError, match="Query must be a non-empty string"):
            await graph_ops.run_cypher("")

        # Test invalid mode
        with pytest.raises(ValueError, match="Mode must be either 'read' or 'write'"):
            await graph_ops.run_cypher("MATCH (n) RETURN n", mode="invalid")

    @pytest.mark.asyncio
    async def test_add_node(self, graph_ops, mock_client):
        """Test adding a node."""
        node_data = {
            "id": "node1",
            "labels": ["Host", "Server"],
            "attrs": {"ip": "192.168.1.1", "name": "web-server"}
        }
        mock_client.call_tool.return_value = {"node": {"id": "node1"}}

        result = await graph_ops.add_node(node_data)

        assert "node" in result
        mock_client.call_tool.assert_called_once()
        call_args = mock_client.call_tool.call_args
        assert "CREATE (n:Host:Server" in call_args[0][1]["query"]

    @pytest.mark.asyncio
    async def test_add_node_validation(self, graph_ops):
        """Test node data validation."""
        # Test invalid node data type
        with pytest.raises(ValueError, match="Node data must be a dictionary"):
            await graph_ops.add_node("invalid")

    @pytest.mark.asyncio
    async def test_add_edge(self, graph_ops, mock_client):
        """Test adding an edge."""
        edge_data = {
            "source": "node1",
            "target": "node2",
            "type": "CONNECTED_TO",
            "attrs": {"port": 80, "protocol": "HTTP"}
        }
        mock_client.call_tool.return_value = {"edge": {"id": "edge1"}}

        result = await graph_ops.add_edge(edge_data)

        assert "edge" in result
        mock_client.call_tool.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_edge_validation(self, graph_ops):
        """Test edge data validation."""
        # Test missing required fields
        with pytest.raises(ValueError, match="Edge data missing required field: source"):
            await graph_ops.add_edge({"target": "node2"})

        with pytest.raises(ValueError, match="Edge data missing required field: target"):
            await graph_ops.add_edge({"source": "node1"})

    @pytest.mark.asyncio
    async def test_update_node(self, graph_ops, mock_client):
        """Test updating a node."""
        mock_client.call_tool.return_value = {"node": {"id": "node1", "updated": True}}

        result = await graph_ops.update_node("node1", {"status": "online"})

        assert result["node"]["updated"] is True
        mock_client.call_tool.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_node_validation(self, graph_ops):
        """Test node update validation."""
        # Test empty node ID
        with pytest.raises(ValueError, match="Node ID must be a non-empty string"):
            await graph_ops.update_node("", {"status": "online"})

        # Test invalid attributes
        with pytest.raises(ValueError, match="Attributes must be a dictionary"):
            await graph_ops.update_node("node1", "invalid")

    @pytest.mark.asyncio
    async def test_delete_node(self, graph_ops, mock_client):
        """Test deleting a node."""
        mock_client.call_tool.return_value = {"deleted_count": 1}

        result = await graph_ops.delete_node("node1")

        assert result["status"] == "deleted"
        assert result["node_id"] == "node1"
        mock_client.call_tool.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_graph(self, graph_ops, mock_client):
        """Test loading a complete graph."""
        graph_payload = {
            "nodes": [
                {"id": "node1", "labels": ["Host"], "attrs": {"ip": "192.168.1.1"}},
                {"id": "node2", "labels": ["Host"], "attrs": {"ip": "192.168.1.2"}},
            ],
            "edges": [
                {"source": "node1", "target": "node2", "type": "CONNECTED", "attrs": {"port": 80}}
            ]
        }

        # Mock successful operations
        mock_client.call_tool.return_value = {"success": True}

        result = await graph_ops.load_graph(graph_payload)

        assert result["nodes_created"] == 2
        assert result["edges_created"] == 1
        assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_load_graph_with_errors(self, graph_ops, mock_client):
        """Test loading graph with some failures."""
        graph_payload = {
            "nodes": [
                {"id": "node1", "labels": ["Host"], "attrs": {"ip": "192.168.1.1"}},
                {"invalid": "node"}  # This should fail
            ],
            "edges": []
        }

        # Mock mixed results - first call succeeds, second fails
        mock_client.call_tool.side_effect = [
            {"success": True},
            Exception("Invalid node data")
        ]

        result = await graph_ops.load_graph(graph_payload)

        assert result["nodes_created"] == 1
        assert result["edges_created"] == 0
        assert len(result["errors"]) == 1
        assert "Invalid node data" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_load_graph_validation(self, graph_ops):
        """Test graph payload validation."""
        # Test invalid payload type
        with pytest.raises(ValueError, match="Graph payload must be a dictionary"):
            await graph_ops.load_graph("invalid")