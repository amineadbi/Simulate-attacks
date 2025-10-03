from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .settings import Settings, get_settings
from ...mcp_integration import MCPGraphOperations
from ...tools import ToolRegistry
from ...caldera.config import CalderaSettings
from ...simulation_engine import configure_caldera_adapter, get_simulation_engine, SimulationPlatform
from ...scenario_templates import create_scenario_from_template
from .error_handling import (
    with_error_handling,
    validate_graph_payload, validate_cypher_query, global_exception_handler
)

logger = logging.getLogger(__name__)

# Global instances
_tool_registry: Optional[ToolRegistry] = None

def get_tool_registry() -> ToolRegistry:
    """Get or create the global tool registry."""
    global _tool_registry
    if _tool_registry is None:
        caldera_settings = CalderaSettings.from_env()
        _tool_registry = ToolRegistry.create_minimal(caldera_settings=caldera_settings)
        logger.info("Created minimal tool registry for API")
        configure_caldera_adapter(caldera_settings)
    return _tool_registry

async def get_mcp_operations() -> MCPGraphOperations:
    """Get or create the global MCP operations instance."""
    registry = get_tool_registry()
    return await registry.get_mcp_operations()

# Main API router
router = APIRouter(prefix="/api", tags=["api"])

# Tools router for frontend compatibility
tools_router = APIRouter(prefix="/tools", tags=["tools"])


class GraphPayload(BaseModel):
    nodes: list[dict] = Field(default_factory=list)
    edges: list[dict] = Field(default_factory=list)


class CypherRequest(BaseModel):
    query: str
    mode: Literal["read", "write"] = "read"
    params: Optional[Dict[str, Any]] = None


class CypherResult(BaseModel):
    records: list[dict] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)


def _map_job_status(status: str) -> str:
    mapping = {
        'initializing': 'pending',
        'pending': 'pending',
        'running': 'running',
        'paused': 'running',
        'completed': 'succeeded',
        'failed': 'failed',
        'cancelled': 'failed',
    }
    return mapping.get(status, status)

def _merge_dict(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_dict(result[key], value)
        else:
            result[key] = value
    return result


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


@tools_router.get("/health")
def tools_health(settings: Settings = Depends(get_settings)):
    """Compatibility endpoint mirroring /api/health on /tools/health."""
    return health(settings)

# Note: /api/chat endpoint removed - frontend uses WebSocket (/ws) for chat


@tools_router.post("/load_graph")
async def load_graph(payload: GraphPayload) -> Dict[str, Any]:
    """Load graph data via MCP and return status."""
    logger.info(f"Received load_graph request with {len(payload.nodes)} nodes and {len(payload.edges)} edges")

    # Validate payload structure
    graph_data = {"nodes": payload.nodes, "edges": payload.edges}
    logger.info(f"Prepared graph data for validation: nodes={len(graph_data['nodes'])}, edges={len(graph_data['edges'])}")
    validate_graph_payload(graph_data)

    # Load graph using GLOBAL MCP operations instance
    async def _load_graph():
        logger.info("Using GLOBAL MCP operations for graph loading...")
        mcp_ops = await get_mcp_operations()
        result = await mcp_ops.load_graph(graph_data)
        logger.info(f"Graph load completed: {result}")
        return result

    logger.info("Starting MCP graph load with error handling...")
    result = await with_error_handling("load_graph", _load_graph)
    logger.info(f"Load graph operation successful: {result}")

    summary = {
        "nodes": result.get("nodes_created", 0),
        "edges": result.get("edges_created", 0),
        "errors": len(result.get("errors", []))
    }

    # Return the result along with the original payload for frontend
    return {
        "status": "success",
        "nodes_created": result.get("nodes_created", 0),
        "edges_created": result.get("edges_created", 0),
        "errors": result.get("errors", []),
        "summary": summary,
        "nodes": payload.nodes,  # For frontend visualization
        "edges": payload.edges   # For frontend visualization
    }


@tools_router.post("/run_cypher")
async def run_cypher(request: CypherRequest) -> CypherResult:
    """Run Cypher query via MCP."""
    # Normalize and validate query and mode
    validate_cypher_query(request.query)
    mode = request.mode.lower()
    if mode not in {"read", "write"}:
        raise HTTPException(status_code=400, detail="Mode must be 'read' or 'write'")

    settings = get_settings()
    if mode == "write" and not settings.allow_write_cypher:
        raise HTTPException(
            status_code=403,
            detail="Write queries are disabled. Set GRAPH_ALLOW_WRITE_CYPHER=true to enable."
        )

    params = request.params or {}
    if not isinstance(params, dict):
        raise HTTPException(status_code=400, detail="Params must be a dictionary if provided")

    # Execute query using GLOBAL MCP operations instance
    async def _run_cypher():
        mcp_ops = await get_mcp_operations()
        return await mcp_ops.run_cypher(
            query=request.query,
            params=params,
            mode=mode
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
    """Start attack simulation using the shared simulation engine."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload must be a dictionary")

    scenario_id = payload.get("scenarioId") or payload.get("scenario_id")
    if not scenario_id:
        raise HTTPException(status_code=400, detail="scenarioId is required")

    platform_value = payload.get("platform", "mock")
    try:
        platform = SimulationPlatform(platform_value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Unsupported platform '{platform_value}'") from exc

    try:
        scenario = create_scenario_from_template(scenario_id, platform=platform)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    params = payload.get("params") or {}
    if params:
        if not isinstance(params, dict):
            raise HTTPException(status_code=400, detail="params must be an object")
        caldera_params = params.get("caldera") if isinstance(params.get("caldera"), dict) else None
        if caldera_params:
            existing_caldera = scenario.parameters.get("caldera", {})
            scenario.parameters["caldera"] = _merge_dict(existing_caldera, caldera_params)
            params = {k: v for k, v in params.items() if k != "caldera"}
        for key, value in params.items():
            scenario.parameters[key] = value

    target_selector = payload.get("targetSelector")
    if target_selector:
        scenario.target_selector.setdefault("query", target_selector)
        scenario.parameters.setdefault("target_selector_query", target_selector)
        scenario.platform_metadata.setdefault("frontend", {})["target_selector"] = target_selector

    engine = get_simulation_engine()
    try:
        job = await engine.start_simulation(scenario)
    except Exception as exc:
        logger.error("Error starting simulation: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to start simulation: {exc}") from exc

    return {
        "jobId": job.job_id,
        "status": _map_job_status(job.status.value),
        "platform": platform.value,
        "scenarioId": scenario.scenario_id,
        "details": f"Simulation started for {scenario.name}",
    }


@tools_router.post("/check_attack")
async def check_attack(payload: dict) -> Dict[str, Any]:
    """Check attack simulation status."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload must be a dictionary")

    job_id = payload.get("job_id") or payload.get("jobId")
    if not job_id:
        raise HTTPException(status_code=400, detail="job_id is required")

    engine = get_simulation_engine()
    job = await engine.get_job_status(job_id)
    if not job:
        return {"jobId": job_id, "status": "unknown", "details": "Job not found"}

    details = job.events[-1].description if job.events else None
    return {
        "jobId": job_id,
        "status": _map_job_status(job.status.value),
        "progress": job.progress_percentage,
        "details": details,
    }


@tools_router.post("/fetch_results")
async def fetch_results(payload: dict) -> Dict[str, Any]:
    """Fetch attack simulation results."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload must be a dictionary")

    job_id = payload.get("job_id") or payload.get("jobId")
    if not job_id:
        raise HTTPException(status_code=400, detail="job_id is required")

    engine = get_simulation_engine()
    job = await engine.get_job_status(job_id)
    if not job:
        return {"jobId": job_id, "status": "unknown", "findings": {}, "platformContext": {}, "details": "Job not found"}

    summary = job.findings.get("summary", {}) if isinstance(job.findings, dict) else {}
    details = summary.get("summary") or summary.get("scenario_name")
    return {
        "jobId": job_id,
        "status": _map_job_status(job.status.value),
        "findings": job.findings,
        "platformContext": job.platform_context,
        "details": details,
    }




async def app_lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Graph MCP API")

    # Initialize tool registry on startup
    registry = get_tool_registry()
    logger.info("Tool registry initialized")

    # Initialize agent app and store in app.state
    try:
        from ...flow import create_application
        logger.info("Creating agent application...")
        agent_app = await create_application()
        app.state.agent_app = agent_app
        logger.info("Agent application created and stored in app.state")
    except Exception as e:
        logger.warning(f"Failed to create agent application: {e}")
        app.state.agent_app = None

    yield

    # Cleanup on shutdown
    global _tool_registry
    try:
        # Close agent app if it exists
        if hasattr(app.state, 'agent_app') and app.state.agent_app:
            await app.state.agent_app.aclose()
            logger.info("Agent app closed")

        await registry.aclose()
        logger.info("Tool registry closed")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
    finally:
        _tool_registry = None

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





