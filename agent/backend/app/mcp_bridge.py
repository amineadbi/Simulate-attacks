"""
Bridge between old REST API and new MCP-based operations.
This allows the frontend to continue using the same API while
we migrate to MCP internally.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent.cypher_operations import CypherGraphOps
from agent.models import Edge, GraphPayload, Node

router = APIRouter(prefix="/tools", tags=["mcp-bridge"])


class UpdateRequest(BaseModel):
    attrs: Dict[str, Any]


class SubgraphRequest(BaseModel):
    node_ids: Optional[List[str]] = None
    limit: Optional[int] = None


class CypherRequest(BaseModel):
    query: str
    params: Optional[Dict[str, Any]] = None
    mode: str = "read"


# This will be injected by the main app
mcp_tools = None


def set_mcp_tools(tools):
    """Set the MCP tools registry."""
    global mcp_tools
    mcp_tools = tools


async def _execute_cypher(query: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Execute a Cypher query via MCP."""
    if not mcp_tools:
        raise HTTPException(status_code=500, detail="MCP tools not available")

    neo4j_client = mcp_tools.get("neo4j")
    result = await neo4j_client.invoke("run-cypher", {
        "query": query,
        "params": params or {}
    })
    return result.response


@router.post("/load_graph")
async def load_graph(payload: GraphPayload):
    """Load a complete graph via MCP Cypher operations."""
    try:
        queries = CypherGraphOps.load_graph(payload)
        results = []

        for query_op in queries:
            result = await _execute_cypher(query_op["query"], query_op["params"])
            results.append(result)

        return {
            "nodes": len(payload.nodes),
            "edges": len(payload.edges),
            "queries_executed": len(queries)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add_node")
async def add_node(node: Node):
    """Add a single node."""
    try:
        cypher_op = CypherGraphOps.add_node(node)
        result = await _execute_cypher(cypher_op["query"], cypher_op["params"])
        return {"status": "created", "node_id": node.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update_node/{node_id}")
async def update_node(node_id: str, request: UpdateRequest):
    """Update node attributes."""
    try:
        cypher_op = CypherGraphOps.update_node(node_id, request.attrs)
        result = await _execute_cypher(cypher_op["query"], cypher_op["params"])
        return {"status": "updated", "node_id": node_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/delete_node/{node_id}")
async def delete_node(node_id: str):
    """Delete a node."""
    try:
        cypher_op = CypherGraphOps.delete_node(node_id)
        result = await _execute_cypher(cypher_op["query"], cypher_op["params"])
        return {"status": "deleted", "node_id": node_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add_edge")
async def add_edge(edge: Edge):
    """Add a single edge."""
    try:
        cypher_op = CypherGraphOps.add_edge(edge)
        result = await _execute_cypher(cypher_op["query"], cypher_op["params"])
        return {"status": "created", "edge_id": edge.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update_edge/{edge_id}")
async def update_edge(edge_id: str, request: UpdateRequest):
    """Update edge attributes."""
    try:
        cypher_op = CypherGraphOps.update_edge(edge_id, request.attrs)
        result = await _execute_cypher(cypher_op["query"], cypher_op["params"])
        return {"status": "updated", "edge_id": edge_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/delete_edge/{edge_id}")
async def delete_edge(edge_id: str):
    """Delete an edge."""
    try:
        cypher_op = CypherGraphOps.delete_edge(edge_id)
        result = await _execute_cypher(cypher_op["query"], cypher_op["params"])
        return {"status": "deleted", "edge_id": edge_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/get_subgraph")
async def get_subgraph(request: SubgraphRequest):
    """Get a subgraph."""
    try:
        cypher_op = CypherGraphOps.get_subgraph(request.node_ids, request.limit)
        result = await _execute_cypher(cypher_op["query"], cypher_op["params"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run_cypher")
async def run_cypher(request: CypherRequest):
    """Execute a custom Cypher query."""
    try:
        result = await _execute_cypher(request.query, request.params)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health():
    """Health check endpoint."""
    try:
        # Test Neo4j connection via MCP
        if mcp_tools:
            neo4j_client = mcp_tools.get("neo4j")
            result = await neo4j_client.invoke("run-cypher", {
                "query": "RETURN 1 as test",
                "params": {}
            })
            return {"status": "ok", "neo4j_via_mcp": True}
        else:
            return {"status": "ok", "neo4j_via_mcp": False}
    except Exception as e:
        return {"status": "error", "error": str(e)}