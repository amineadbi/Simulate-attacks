"""
Integration tests for the updated FastAPI backend with MCP integration.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock

from agent.backend.app.api import build_app
from agent.simulation_engine import SimulationPlatform

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




class DummyStatus:
    def __init__(self, value: str):
        self.value = value


class DummyEvent:
    def __init__(self, description: str):
        self.description = description


class DummyJob:
    def __init__(self, job_id: str, *, status: str = "initializing", progress: float = 0.0,
                 findings: dict | None = None, platform_context: dict | None = None,
                 events: list | None = None):
        self.job_id = job_id
        self.status = DummyStatus(status)
        self.progress_percentage = progress
        self.findings = findings or {}
        self.platform_context = platform_context or {}
        self.events = events or []


class DummyEngine:
    def __init__(self):
        self.jobs: dict[str, DummyJob] = {}
        self.started_scenarios = []
        self.platform_adapters: dict = {}

    async def start_simulation(self, scenario):
        job_id = f"job-{len(self.jobs) + 1:03d}"
        job = DummyJob(job_id)
        self.jobs[job_id] = job
        self.started_scenarios.append(scenario)
        return job

    async def get_job_status(self, job_id: str):
        return self.jobs.get(job_id)


@pytest.fixture
def mock_simulation_engine(monkeypatch):
    engine = DummyEngine()
    engine.platform_adapters = {
        SimulationPlatform.MOCK: object(),
        SimulationPlatform.CALDERA: object(),
    }
    monkeypatch.setattr('agent.backend.app.api.get_simulation_engine', lambda: engine)
    return engine


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
        assert data["summary"]["nodes"] == 2
        assert data["summary"]["edges"] == 1
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
        assert data["summary"]["nodes"] == 1
        assert data["summary"]["edges"] == 0
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
        assert data == mock_mcp_ops.run_cypher.return_value
        mock_mcp_ops.run_cypher.assert_awaited_once_with(
            query="MATCH (n) RETURN n.id, n.name LIMIT 1",
            params={},
            mode="read"
        )

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

    @patch('agent.backend.app.api.get_settings')
    @patch('agent.backend.app.api.get_tool_registry')
    def test_run_cypher_write_mode(self, mock_get_registry, mock_get_settings, client, mock_tool_registry):
        """Test Cypher query in write mode when enabled."""
        mock_get_registry.return_value = mock_tool_registry
        mock_get_settings.return_value = Settings(allow_write_cypher=True)
        mock_mcp_ops = mock_tool_registry.get_mcp_operations.return_value
        mock_mcp_ops.run_cypher.return_value = {
            "records": [],
            "summary": {"nodes_created": 1}
        }

        payload = {
            "query": "CREATE (n:Test {name: 'test'}) RETURN n",
            "mode": "write",
            "params": {"name": "test"}
        }

        response = client.post("/tools/run_cypher", json=payload)
        assert response.status_code == 200

        mock_mcp_ops.run_cypher.assert_awaited_once_with(
            query=payload["query"],
            params={"name": "test"},
            mode="write"
        )


class TestSimulationEndpoints:
    """Test attack simulation endpoints."""

    def test_start_attack_success(self, client, mock_simulation_engine):
        """Test starting attack simulation."""
        payload = {
            "platform": "mock",
            "scenarioId": "lateral_movement"
        }

        response = client.post("/tools/start_attack", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["jobId"].startswith("job-")
        assert data["status"] == "pending"
        assert data["platform"] == "mock"
        assert data["scenarioId"] == "lateral_movement"
        assert mock_simulation_engine.started_scenarios

    def test_start_attack_caldera_merges_params(self, client, mock_simulation_engine):
        payload = {
            "platform": "caldera",
            "scenarioId": "lateral_movement",
            "params": {
                "caldera": {
                    "operation": {
                        "planner": "batch",
                        "visibility": 80
                    }
                },
                "stealth_level": "high"
            }
        }

        response = client.post("/tools/start_attack", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["platform"] == "caldera"

        scenario = mock_simulation_engine.started_scenarios[-1]
        caldera_params = scenario.parameters.get("caldera", {})
        operation_cfg = caldera_params.get("operation", {})
        assert operation_cfg.get("planner") == "batch"
        assert operation_cfg.get("autonomous") == 1
        assert scenario.parameters.get("stealth_level") == "high"

    def test_start_attack_invalid_payload(self, client):
        """Test starting attack with invalid payload."""
        response = client.post("/tools/start_attack", json="invalid")
        assert response.status_code == 400
        assert "detail" in response.json()

    def test_start_attack_missing_scenario(self, client):
        """Scenario ID is required."""
        response = client.post("/tools/start_attack", json={"platform": "mock"})
        assert response.status_code == 400

    def test_check_attack_status(self, client, mock_simulation_engine):
        """Test checking attack status."""
        mock_simulation_engine.jobs["sim-test123"] = DummyJob(
            job_id="sim-test123",
            status="running",
            progress=42.5,
            events=[DummyEvent("Running step 1")],
        )

        response = client.post("/tools/check_attack", json={"job_id": "sim-test123"})
        assert response.status_code == 200

        data = response.json()
        assert data["jobId"] == "sim-test123"
        assert data["status"] == "running"
        assert data["progress"] == pytest.approx(42.5)
        assert data["details"] == "Running step 1"

    def test_check_attack_missing_job_id(self, client):
        """Test checking attack status without job ID."""
        response = client.post("/tools/check_attack", json={})
        assert response.status_code == 400

    def test_fetch_results_success(self, client, mock_simulation_engine):
        """Test fetching attack results."""
        mock_simulation_engine.jobs["sim-test123"] = DummyJob(
            job_id="sim-test123",
            status="completed",
            progress=100.0,
            findings={"summary": {"scenario_name": "Test Scenario", "summary": "Completed"}},
            platform_context={"caldera": {"operation_id": "op-123"}},
        )

        response = client.post("/tools/fetch_results", json={"job_id": "sim-test123"})
        assert response.status_code == 200

        data = response.json()
        assert data["jobId"] == "sim-test123"
        assert data["status"] == "succeeded"
        assert isinstance(data["findings"], dict)
        assert data["platformContext"]["caldera"]["operation_id"] == "op-123"
        assert data["details"] == "Completed"

    def test_fetch_results_unknown_job(self, client, mock_simulation_engine):
        """Test fetching results for unknown job."""
        response = client.post("/tools/fetch_results", json={"job_id": "unknown-job"})
        assert response.status_code == 200

        data = response.json()
        assert data["jobId"] == "unknown-job"
        assert data["status"] == "unknown"
        assert data["findings"] == {}
        assert data["platformContext"] == {}


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

