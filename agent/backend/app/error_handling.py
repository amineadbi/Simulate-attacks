"""
Error handling utilities for the backend application.
Provides standardized error responses and exception handling.
"""
from __future__ import annotations

import logging
import traceback
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class MCPError(Exception):
    """Base exception for MCP-related errors."""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error


class GraphOperationError(MCPError):
    """Exception for graph operation failures."""

    def __init__(self, operation: str, message: str, original_error: Optional[Exception] = None):
        super().__init__(f"Graph operation '{operation}' failed: {message}", original_error)
        self.operation = operation


class ValidationError(Exception):
    """Exception for validation failures."""

    def __init__(self, field: str, value: Any, message: str):
        super().__init__(f"Validation failed for field '{field}': {message}")
        self.field = field
        self.value = value


def create_error_response(
    status_code: int,
    message: str,
    error_type: str = "error",
    details: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    """Create standardized error response."""
    content = {
        "error": {
            "type": error_type,
            "message": message,
            "status_code": status_code
        }
    }

    if details:
        content["error"]["details"] = details

    return JSONResponse(
        status_code=status_code,
        content=content
    )


async def global_exception_handler(request: Request, exc: Exception) -> Response:
    """Global exception handler for the application."""

    # Log the exception
    logger.error(f"Unhandled exception in {request.method} {request.url}: {exc}")
    logger.error(traceback.format_exc())

    # Handle different exception types
    if isinstance(exc, HTTPException):
        return create_error_response(
            status_code=exc.status_code,
            message=exc.detail,
            error_type="http_exception"
        )

    elif isinstance(exc, MCPError):
        details = {}
        if exc.original_error:
            details["original_error"] = str(exc.original_error)
            details["original_error_type"] = type(exc.original_error).__name__

        return create_error_response(
            status_code=500,
            message=str(exc),
            error_type="mcp_error",
            details=details
        )

    elif isinstance(exc, ValidationError):
        return create_error_response(
            status_code=400,
            message=str(exc),
            error_type="validation_error",
            details={
                "field": exc.field,
                "value": str(exc.value) if exc.value is not None else None
            }
        )

    else:
        # Generic server error
        return create_error_response(
            status_code=500,
            message="An unexpected error occurred",
            error_type="internal_server_error",
            details={
                "exception_type": type(exc).__name__
            }
        )


def validate_graph_payload(payload: Dict[str, Any]) -> None:
    """Validate graph payload structure."""
    logger.info(f"🔍 Validating graph payload: {type(payload)}")

    if not isinstance(payload, dict):
        logger.error(f"❌ Payload validation failed: expected dict, got {type(payload)}")
        raise ValidationError("payload", payload, "Must be a dictionary")

    logger.info(f"📊 Payload keys: {list(payload.keys())}")

    # Validate nodes
    nodes = payload.get("nodes", [])
    logger.info(f"📦 Found {len(nodes) if isinstance(nodes, list) else 'invalid'} nodes")

    if not isinstance(nodes, list):
        logger.error(f"❌ Nodes validation failed: expected list, got {type(nodes)}")
        raise ValidationError("nodes", nodes, "Must be a list")

    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            logger.error(f"❌ Node[{i}] validation failed: expected dict, got {type(node)}")
            raise ValidationError(f"nodes[{i}]", node, "Must be a dictionary")

        # Check for required ID field
        if "id" not in node:
            logger.error(f"❌ Node[{i}] missing required 'id' field: {node}")
            raise ValidationError(f"nodes[{i}].id", None, "Node must have an 'id' field")

    # Validate edges
    edges = payload.get("edges", [])
    logger.info(f"🔗 Found {len(edges) if isinstance(edges, list) else 'invalid'} edges")

    if not isinstance(edges, list):
        logger.error(f"❌ Edges validation failed: expected list, got {type(edges)}")
        raise ValidationError("edges", edges, "Must be a list")

    for i, edge in enumerate(edges):
        if not isinstance(edge, dict):
            logger.error(f"❌ Edge[{i}] validation failed: expected dict, got {type(edge)}")
            raise ValidationError(f"edges[{i}]", edge, "Must be a dictionary")

        # Check for required source and target fields
        if "source" not in edge:
            logger.error(f"❌ Edge[{i}] missing required 'source' field: {edge}")
            raise ValidationError(f"edges[{i}].source", None, "Edge must have a 'source' field")
        if "target" not in edge:
            logger.error(f"❌ Edge[{i}] missing required 'target' field: {edge}")
            raise ValidationError(f"edges[{i}].target", None, "Edge must have a 'target' field")

    logger.info("✅ Graph payload validation successful")


def validate_cypher_query(query: str) -> None:
    """Basic validation for Cypher queries."""
    if not isinstance(query, str):
        raise ValidationError("query", query, "Must be a string")

    if not query.strip():
        raise ValidationError("query", query, "Cannot be empty")

    # Basic security checks - prevent obviously dangerous queries
    dangerous_keywords = ["DROP", "DELETE ALL", "DETACH DELETE ALL"]
    query_upper = query.upper()

    for keyword in dangerous_keywords:
        if keyword in query_upper:
            logger.warning(f"Potentially dangerous query detected: {query[:100]}...")
            # For now, we'll log but not block - in production you might want to block
            break


def handle_mcp_operation_error(operation: str, error: Exception) -> GraphOperationError:
    """Convert generic exceptions to GraphOperationError."""
    error_message = str(error)

    # Extract meaningful error messages from common error types
    if "connection" in error_message.lower():
        error_message = "Failed to connect to Neo4j database"
    elif "timeout" in error_message.lower():
        error_message = "Operation timed out"
    elif "authentication" in error_message.lower():
        error_message = "Authentication failed"
    elif "cypher" in error_message.lower():
        error_message = "Invalid Cypher query"

    return GraphOperationError(operation, error_message, error)


async def with_error_handling(operation: str, func, *args, **kwargs):
    """Wrapper for handling MCP operations with standardized error handling."""
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Error in {operation}: {e}")
        raise handle_mcp_operation_error(operation, e)