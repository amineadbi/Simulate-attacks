"""
Integration tests for the updated FastAPI backend with MCP integration.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock

from agent.backend.app.api import build_app


@pytest.fixture
def app():
    """Create FastAPI app for testing."""
    return build_app()


@pytest.fixture
def client(app):
    """Create test client with mocked dependencies."""
    return TestClient(app)


@pytest.fixture
def mock_tool_registry():
    """Create mock tool registry."""
    registry = AsyncMock()
    registry.get_mcp_client.return_value = AsyncMock()
    registry.get_mcp_operations.return_value = AsyncMock()
    return registry


class TestHealthEndpoint:
    """Test health endpoint functionality."""

    def test_health_endpoint_success(self, client):
        """Test health endpoint returns correct status."""
        response = client.get("/api/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert data["architecture"] == "mcp"
        assert "details" in data
        assert data["details"]["mcp_enabled"] is True


class TestGraphOperations:
    """Test graph operation endpoints."""

    @patch('agent.backend.app.api.get_tool_registry')
    def test_load_graph_success(self, mock_get_registry, client, mock_tool_registry):
        """Test successful graph loading."""
        # Setup mock
        mock_get_registry.return_value = mock_tool_registry
        mock_mcp_ops = mock_tool_registry.get_mcp_operations.return_value
        mock_mcp_ops.load_graph.return_value = {
            "nodes_created": 2,
            "edges_created": 1,
            "errors": []
        }

        payload = {
            "nodes": [
                {"id": "n1", "labels": ["Host"], "attrs": {"ip": "10.0.0.1"}},
                {"id": "n2", "labels": ["Host"], "attrs": {"ip": "10.0.0.2"}},
            ],
            "edges": [
                {
                    "source": "n1",
                    "target": "n2",
                    "type": "allowed_tcp",
                    "attrs": {"port": 445},
                }
            ],
        }

        response = client.post("/tools/load_graph", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"
        assert data["nodes_created"] == 2
        assert data["edges_created"] == 1
        assert len(data["errors"]) == 0
        # Should include original payload for frontend
        assert "nodes" in data
        assert "edges" in data

    def test_load_graph_validation_error(self, client):
        """Test graph loading with invalid payload."""
        # Missing required 'id' field in node
        payload = {
            "nodes": [
                {"labels": ["Host"], "attrs": {"ip": "10.0.0.1"}},  # Missing 'id'
            ],
            "edges": [],
        }

        response = client.post("/tools/load_graph", json=payload)
        assert response.status_code == 400

        data = response.json()
        assert "error" in data
        assert data["error"]["type"] == "validation_error"
        assert "id" in data["error"]["message"]

    @patch('agent.backend.app.api.get_tool_registry')
    def test_load_graph_with_errors(self, mock_get_registry, client, mock_tool_registry):
        """Test graph loading with partial failures."""
        mock_get_registry.return_value = mock_tool_registry
        mock_mcp_ops = mock_tool_registry.get_mcp_operations.return_value
        mock_mcp_ops.load_graph.return_value = {
            "nodes_created": 1,
            "edges_created": 0,
            "errors": ["Failed to create node n2: Invalid data"]
        }

        payload = {
            "nodes": [{"id": "n1", "labels": ["Host"], "attrs": {"ip": "10.0.0.1"}}],
            "edges": []
        }

        response = client.post("/tools/load_graph", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["nodes_created"] == 1
        assert len(data["errors"]) == 1


class TestCypherOperations:
    """Test Cypher query endpoint."""

    @patch('agent.backend.app.api.get_tool_registry')
    def test_run_cypher_success(self, mock_get_registry, client, mock_tool_registry):
        """Test successful Cypher query execution."""
        mock_get_registry.return_value = mock_tool_registry
        mock_mcp_ops = mock_tool_registry.get_mcp_operations.return_value
        mock_mcp_ops.run_cypher.return_value = {
            "records": [{"n.id": "node1", "n.name": "Test Node"}],
            "summary": {"nodes_returned": 1}
        }

        payload = {
            "query": "MATCH (n) RETURN n.id, n.name LIMIT 1",
            "mode": "read"
        }

        response = client.post("/tools/run_cypher", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "records" in data
        assert "summary" in data
        assert len(data["records"]) == 1
        assert data["records"][0]["n.id"] == "node1"

    def test_run_cypher_empty_query(self, client):
        """Test Cypher query with empty query string."""
        payload = {
            "query": "",  # Empty query
            "mode": "read"
        }

        response = client.post("/tools/run_cypher", json=payload)
        assert response.status_code == 400

        data = response.json()
        assert "error" in data
        assert data["error"]["type"] == "validation_error"

    def test_run_cypher_whitespace_only(self, client):
        """Test Cypher query with whitespace-only query."""
        payload = {
            "query": "   \n\t   ",  # Whitespace only
            "mode": "read"
        }

        response = client.post("/tools/run_cypher", json=payload)
        assert response.status_code == 400

    @patch('agent.backend.app.api.get_tool_registry')
    def test_run_cypher_write_mode(self, mock_get_registry, client, mock_tool_registry):
        """Test Cypher query in write mode."""
        mock_get_registry.return_value = mock_tool_registry
        mock_mcp_ops = mock_tool_registry.get_mcp_operations.return_value
        mock_mcp_ops.run_cypher.return_value = {
            "records": [],
            "summary": {"nodes_created": 1}
        }

        payload = {
            "query": "CREATE (n:Test {name: 'test'}) RETURN n",
            "mode": "write"
        }

        response = client.post("/tools/run_cypher", json=payload)
        assert response.status_code == 200

        # Verify write mode was passed to MCP operations
        mock_mcp_ops.run_cypher.assert_called_once()
        call_args = mock_mcp_ops.run_cypher.call_args
        assert call_args[1]["mode"] == "write"


class TestSimulationEndpoints:
    """Test attack simulation endpoints."""

    def test_start_attack_success(self, client):
        """Test starting attack simulation."""
        payload = {
            "platform": "test",
            "target": "192.168.1.0/24"
        }

        response = client.post("/tools/start_attack", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "job_id" in data
        assert "status" in data
        assert data["status"] == "started"
        assert data["platform"] == "test"

    def test_start_attack_invalid_payload(self, client):
        """Test starting attack with invalid payload."""
        response = client.post("/tools/start_attack", json="invalid")
        assert response.status_code == 400

        data = response.json()
        assert "error" in data

    def test_check_attack_status(self, client):
        """Test checking attack status."""
        payload = {"job_id": "sim-test123"}

        response = client.post("/tools/check_attack", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "job_id" in data
        assert "status" in data
        assert data["job_id"] == "sim-test123"

    def test_check_attack_missing_job_id(self, client):
        """Test checking attack status without job ID."""
        response = client.post("/tools/check_attack", json={})
        assert response.status_code == 400

        data = response.json()
        assert "error" in data

    def test_fetch_results_success(self, client):
        """Test fetching attack results."""
        payload = {"job_id": "sim-test123"}

        response = client.post("/tools/fetch_results", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "job_id" in data
        assert "findings" in data
        assert "recommendations" in data
        assert data["job_id"] == "sim-test123"
        assert isinstance(data["findings"], list)
        assert isinstance(data["recommendations"], list)

    def test_fetch_results_unknown_job(self, client):
        """Test fetching results for unknown job."""
        payload = {"job_id": "unknown-job"}

        response = client.post("/tools/fetch_results", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["job_id"] == "unknown-job"
        assert len(data["findings"]) == 0
        assert len(data["recommendations"]) == 0
        assert "No results found" in data["message"]


class TestErrorHandling:
    """Test error handling across endpoints."""

    @patch('agent.backend.app.api.get_tool_registry')
    def test_mcp_connection_error(self, mock_get_registry, client):
        """Test handling of MCP connection errors."""
        # Mock registry that raises connection error
        mock_registry = AsyncMock()
        mock_registry.get_mcp_client.side_effect = Exception("Connection failed")
        mock_get_registry.return_value = mock_registry

        payload = {
            "nodes": [{"id": "n1", "labels": ["Host"], "attrs": {"ip": "10.0.0.1"}}],
            "edges": []
        }

        response = client.post("/tools/load_graph", json=payload)
        assert response.status_code == 500

        data = response.json()
        assert "error" in data
        assert "Failed to load graph" in data["error"]["message"]

    def test_invalid_json_payload(self, client):
        """Test handling of invalid JSON in request."""
        response = client.post(
            "/tools/load_graph",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422  # Unprocessable Entity from FastAPI

    def test_missing_required_fields(self, client):
        """Test handling of missing required fields in Pydantic models."""
        # Send payload without required 'nodes' and 'edges' fields
        response = client.post("/tools/load_graph", json={})

        # FastAPI should handle this with Pydantic validation
        assert response.status_code == 422