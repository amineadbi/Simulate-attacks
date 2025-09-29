from __future__ import annotations

from fastapi import FastAPI

from .api import build_app

# Create the FastAPI app without the deprecated MCP HTTP integration
# The MCP integration now uses stdio transport directly from the agent
app: FastAPI = build_app()


def get_app() -> FastAPI:
    return app

