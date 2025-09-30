from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .settings import Settings, get_settings
from ...mcp_integration import MCPGraphOperations, Neo4jMCPClient
from ...tools import ToolRegistry
from .error_handling import (
    with_error_handling,
    validate_graph_payload, validate_cypher_query, global_exception_handler
)

logger = logging.getLogger(__name__)

# Global tool registry instance
_tool_registry: Optional[ToolRegistry] = None

def get_tool_registry() -> ToolRegistry:
    """Get or create the global tool registry."""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry.create_minimal()
        logger.info("Created minimal tool registry for API")
    return _tool_registry

# Main API router
router = APIRouter(prefix="/api", tags=["api"])

# Tools router for frontend compatibility
tools_router = APIRouter(prefix="/tools", tags=["tools"])


class GraphPayload(BaseModel):
    nodes: list[dict] = []
    edges: list[dict] = []


class CypherRequest(BaseModel):
    query: str
    mode: str = "read"


class CypherResult(BaseModel):
    records: list[dict] = []
    summary: dict = {}


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    message: str
    timestamp: str


@router.get("/health")
def health(settings: Settings = Depends(get_settings)):
    return {
        "status": "ok",
        "architecture": "mcp",
        "details": {
            "mcp_enabled": True,
            "neo4j_configured": settings.neo4j_uri is not None,
            "components": ["agent", "websocket", "neo4j-mcp-server"]
        }
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Simple chat endpoint that invokes the LangGraph agent."""
    from datetime import datetime
    from langchain_core.messages import HumanMessage
    from ...flow import create_application

    logger.info(f"💬 Chat request received: {request.message}")

    try:
        # Create and invoke agent
        logger.info("🚀 Creating agent application...")
        agent_app = await create_application()

        if agent_app and agent_app.graph:
            logger.info("🤖 Invoking LangGraph agent...")
            agent_input = {
                "messages": [HumanMessage(content=request.message)]
            }

            result = await agent_app.graph.ainvoke(agent_input)
            logger.info("✅ Agent execution completed")

            # Extract response
            if "messages" in result and result["messages"]:
                last_message = result["messages"][-1]
                response_text = last_message.content if hasattr(last_message, 'content') else str(last_message)
            else:
                response_text = "Agent completed but generated no response."

            return ChatResponse(
                message=response_text,
                timestamp=datetime.utcnow().isoformat() + "Z"
            )
        else:
            logger.error("❌ Agent app not available")
            return ChatResponse(
                message="Agent is not available at this time.",
                timestamp=datetime.utcnow().isoformat() + "Z"
            )

    except Exception as e:
        logger.error(f"❌ Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


@tools_router.post("/load_graph")
async def load_graph(payload: GraphPayload) -> Dict[str, Any]:
    """Load graph data via MCP and return status."""
    logger.info(f"🚀 Received load_graph request with {len(payload.nodes)} nodes and {len(payload.edges)} edges")

    # Validate payload structure
    graph_data = {"nodes": payload.nodes, "edges": payload.edges}
    logger.info(f"📝 Prepared graph data for validation: nodes={len(graph_data['nodes'])}, edges={len(graph_data['edges'])}")
    validate_graph_payload(graph_data)

    # Load graph with proper MCP integration
    async def _load_graph():
        logger.info("🔄 Initializing MCP client for graph loading...")
        mcp_client = Neo4jMCPClient()
        async with mcp_client:
            logger.info("✅ MCP client context established")
            mcp_ops = MCPGraphOperations(mcp_client)
            logger.info("🚀 Executing graph load operation...")
            result = await mcp_ops.load_graph(graph_data)
            logger.info(f"✅ Graph load completed: {result}")
            return result

    logger.info("📡 Starting MCP graph load with error handling...")
    result = await with_error_handling("load_graph", _load_graph)
    logger.info(f"🎉 Load graph operation successful: {result}")

    # Return the result along with the original payload for frontend
    return {
        "status": "success",
        "nodes_created": result.get("nodes_created", 0),
        "edges_created": result.get("edges_created", 0),
        "errors": result.get("errors", []),
        "nodes": payload.nodes,  # For frontend visualization
        "edges": payload.edges   # For frontend visualization
    }


@tools_router.post("/run_cypher")
async def run_cypher(request: CypherRequest) -> CypherResult:
    """Run Cypher query via MCP."""
    # Validate query
    validate_cypher_query(request.query)

    # Execute query with proper MCP integration
    async def _run_cypher():
        mcp_client = Neo4jMCPClient()
        async with mcp_client:
            mcp_ops = MCPGraphOperations(mcp_client)
            return await mcp_ops.run_cypher(
                query=request.query,
                mode=request.mode
            )

    result = await with_error_handling("run_cypher", _run_cypher)

    # Extract records and summary from MCP result
    records = result.get("records", [])
    summary = result.get("summary", {})

    # Ensure records is a list
    if not isinstance(records, list):
        records = []

    # Ensure summary is a dict
    if not isinstance(summary, dict):
        summary = {"message": str(summary)}

    return CypherResult(
        records=records,
        summary=summary
    )


@tools_router.post("/start_attack")
async def start_attack(payload: dict) -> Dict[str, Any]:
    """Start attack simulation."""
    try:
        # Basic validation
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Payload must be a dictionary")

        # For now, we'll import and use the simulation engine if available
        try:
            from ...simulation_engine import SimulationEngine
            engine = SimulationEngine()
            job_id = await engine.start_simulation(payload)

            return {
                "job_id": job_id,
                "status": "started",
                "platform": payload.get("platform", "unknown")
            }
        except ImportError:
            # Fallback to enhanced mock response with unique job ID
            import uuid
            job_id = f"sim-{uuid.uuid4().hex[:8]}"

            logger.warning("Simulation engine not available, using mock response")
            return {
                "job_id": job_id,
                "status": "started",
                "platform": payload.get("platform", "mock"),
                "message": "Simulation engine not integrated - mock response"
            }

    except Exception as e:
        logger.error(f"Error starting attack simulation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start simulation: {str(e)}")


@tools_router.post("/check_attack")
async def check_attack(payload: dict) -> Dict[str, Any]:
    """Check attack simulation status."""
    try:
        job_id = payload.get("job_id")
        if not job_id:
            raise HTTPException(status_code=400, detail="job_id is required")

        # Try to use the simulation engine if available
        try:
            from ...simulation_engine import SimulationEngine
            engine = SimulationEngine()
            status = await engine.check_simulation_status(job_id)
            return status
        except ImportError:
            # Enhanced mock response
            logger.warning("Simulation engine not available, using mock response")

            # Simple mock logic based on job ID
            if job_id.startswith("sim-"):
                return {
                    "job_id": job_id,
                    "status": "completed",
                    "progress": 100,
                    "message": "Mock simulation completed"
                }
            else:
                return {
                    "job_id": job_id,
                    "status": "unknown",
                    "progress": 0,
                    "message": "Job not found in mock system"
                }

    except Exception as e:
        logger.error(f"Error checking attack status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to check status: {str(e)}")


@tools_router.post("/fetch_results")
async def fetch_results(payload: dict) -> Dict[str, Any]:
    """Fetch attack simulation results."""
    try:
        job_id = payload.get("job_id")
        if not job_id:
            raise HTTPException(status_code=400, detail="job_id is required")

        # Try to use the simulation engine if available
        try:
            from ...simulation_engine import SimulationEngine
            engine = SimulationEngine()
            results = await engine.get_simulation_results(job_id)
            return results
        except ImportError:
            # Enhanced mock response with more realistic data
            logger.warning("Simulation engine not available, using mock response")

            if job_id.startswith("sim-"):
                return {
                    "job_id": job_id,
                    "findings": [
                        "Network reconnaissance successful",
                        "Privilege escalation possible via unpatched service",
                        "Lateral movement through SMB shares detected",
                        "Data exfiltration pathways identified"
                    ],
                    "recommendations": [
                        "Apply security patches to identified services",
                        "Implement network segmentation",
                        "Review and restrict SMB share permissions",
                        "Deploy endpoint detection and response (EDR) solutions",
                        "Implement zero-trust network architecture"
                    ],
                    "severity": "high",
                    "affected_nodes": ["server1", "workstation3", "database2"]
                }
            else:
                return {
                    "job_id": job_id,
                    "findings": [],
                    "recommendations": [],
                    "message": "No results found for this job ID"
                }

    except Exception as e:
        logger.error(f"Error fetching results: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch results: {str(e)}")


async def app_lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Graph MCP API")

    # Initialize tool registry on startup
    registry = get_tool_registry()
    logger.info("Tool registry initialized")

    yield

    # Cleanup on shutdown
    try:
        await registry.aclose()
        logger.info("Tool registry closed")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

    logger.info("Graph MCP API shutdown complete")


def build_app(*, lifespan: Optional[Any] = None) -> FastAPI:
    """Build FastAPI application with proper lifespan management."""
    # Use our lifespan if none provided
    if lifespan is None:
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def default_lifespan(app: FastAPI):
            async for _ in app_lifespan(app):
                yield

        lifespan = default_lifespan

    app = FastAPI(
        title="Graph MCP API",
        description="Network security graph analysis with MCP integration",
        version="1.0.0",
        lifespan=lifespan
    )

    # Add global exception handler
    app.add_exception_handler(Exception, global_exception_handler)

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routers
    app.include_router(router)  # /api/* endpoints
    app.include_router(tools_router)  # /tools/* endpoints for frontend compatibility

    # Include WebSocket router for agent communication
    from . import websocket as websocket_module
    app.include_router(websocket_module.router)

    return app

