from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from agent.backend.app.main import build_app


@pytest.fixture()
def client():
    app = build_app()
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoints(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"

    compat_response = client.get("/tools/health")
    assert compat_response.status_code == 200
    assert compat_response.json()["status"] == "ok"


def test_load_graph_roundtrip(client):
    payload = {
        "version": "1.0",
        "metadata": {"source": "test"},
        "nodes": [
            {"id": "n1", "labels": ["Host"], "attrs": {"ip": "10.0.0.1"}},
            {"id": "n2", "labels": ["Host"], "attrs": {"ip": "10.0.0.2"}},
        ],
        "edges": [
            {
                "id": "e1",
                "source": "n1",
                "target": "n2",
                "type": "allowed_tcp",
                "attrs": {"port": 445},
            }
        ],
    }

    mock_ops = AsyncMock()
    mock_ops.load_graph = AsyncMock(
        return_value={"nodes_created": 2, "edges_created": 1, "errors": []}
    )

    with patch("agent.backend.app.api.get_mcp_operations", new=AsyncMock(return_value=mock_ops)):
        response = client.post("/tools/load_graph", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["nodes"] == 2
    assert data["summary"]["edges"] == 1
    assert data["nodes"] == payload["nodes"]
    assert data["edges"] == payload["edges"]


def test_run_cypher_read_mode(client):
    expected_result = {
        "records": [{"n": {"id": "n1"}}],
        "summary": {"nodes": 1}
    }
    mock_ops = AsyncMock()
    mock_ops.run_cypher = AsyncMock(return_value=expected_result)

    payload = {
        "query": "MATCH (n) RETURN n",
        "mode": "read",
        "params": {"limit": 5}
    }

    with patch("agent.backend.app.api.get_mcp_operations", new=AsyncMock(return_value=mock_ops)):
        response = client.post("/tools/run_cypher", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data == expected_result
    mock_ops.run_cypher.assert_awaited_once_with(
        query="MATCH (n) RETURN n",
        params={"limit": 5},
        mode="read"
    )


def test_run_cypher_blocks_write_when_disabled(client):
    payload = {
        "query": "CREATE (n {id: 'n1'}) RETURN n",
        "mode": "write"
    }

    mock_get_ops = AsyncMock()

    with patch("agent.backend.app.api.get_mcp_operations", new=mock_get_ops):
        response = client.post("/tools/run_cypher", json=payload)

    assert response.status_code == 403
    assert mock_get_ops.await_count == 0
