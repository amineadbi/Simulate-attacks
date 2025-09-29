from fastapi.testclient import TestClient

from agent.backend.app import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/tools/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_load_graph_roundtrip():
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
    response = client.post("/tools/load_graph", json=payload)
    assert response.status_code == 200
    summary = response.json()
    assert summary == {"nodes": 2, "edges": 1}

    subgraph = client.post("/tools/get_subgraph", json={"node_ids": ["n1", "n2"]})
    assert subgraph.status_code == 200
    data = subgraph.json()
    assert len(data["nodes"]) == 2
    assert len(data["edges"]) == 1

def test_mcp_manifest():
    response = client.get("/mcp/manifest.json")
    assert response.status_code == 200
    data = response.json()
    assert data.get("name") == "Graph Tool Suite"
