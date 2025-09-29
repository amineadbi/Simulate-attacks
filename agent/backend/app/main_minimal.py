"""
Minimal Backend for MCP Architecture
Handles only agent orchestration and WebSocket communication.
Graph operations are delegated to Neo4j MCP server.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Only import what we need for orchestration
from . import websocket as websocket_module

def build_minimal_app() -> FastAPI:
    """Build minimal FastAPI app for agent orchestration only."""
    app = FastAPI(
        title="BNP Agent Orchestrator",
        description="Minimal backend for LangGraph agent with MCP integration",
        version="2.0.0"
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    @app.get("/health")
    def health():
        return {"status": "ok", "architecture": "mcp", "components": ["agent", "websocket"]}

    # Include only WebSocket router (no graph API routes)
    app.include_router(websocket_module.router)

    return app

# Create the app instance
app = build_minimal_app()