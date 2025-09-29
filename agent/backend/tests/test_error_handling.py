"""
Tests for error handling utilities.
"""
import pytest
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from unittest.mock import MagicMock

from agent.backend.app.error_handling import (
    MCPError, GraphOperationError, ValidationError,
    create_error_response, global_exception_handler,
    validate_graph_payload, validate_cypher_query,
    handle_mcp_operation_error, with_error_handling
)


class TestCustomExceptions:
    """Test custom exception classes."""

    def test_mcp_error_basic(self):
        """Test basic MCP error creation."""
        error = MCPError("Test error")
        assert str(error) == "Test error"
        assert error.original_error is None

    def test_mcp_error_with_original(self):
        """Test MCP error with original exception."""
        original = ValueError("Original error")
        error = MCPError("Wrapper error", original)
        assert str(error) == "Wrapper error"
        assert error.original_error is original

    def test_graph_operation_error(self):
        """Test graph operation error."""
        error = GraphOperationError("add_node", "Failed to add node")
        assert "add_node" in str(error)
        assert "Failed to add node" in str(error)
        assert error.operation == "add_node"

    def test_validation_error(self):
        """Test validation error."""
        error = ValidationError("field_name", "invalid_value", "Must be a string")
        assert "field_name" in str(error)
        assert "Must be a string" in str(error)
        assert error.field == "field_name"
        assert error.value == "invalid_value"


class TestErrorResponseCreation:
    """Test error response creation utilities."""

    def test_create_error_response_basic(self):
        """Test basic error response creation."""
        response = create_error_response(400, "Test error")

        assert isinstance(response, JSONResponse)
        assert response.status_code == 400

        # Check response content
        content = response.body.decode()
        assert "Test error" in content
        assert "error" in content

    def test_create_error_response_with_details(self):
        """Test error response with additional details."""
        details = {"field": "test_field", "value": "test_value"}
        response = create_error_response(
            status_code=422,
            message="Validation failed",
            error_type="validation_error",
            details=details
        )

        assert response.status_code == 422

        # Parse JSON response
        import json
        content = json.loads(response.body.decode())
        assert content["error"]["type"] == "validation_error"
        assert content["error"]["details"]["field"] == "test_field"


class TestGlobalExceptionHandler:
    """Test global exception handler."""

    @pytest.fixture
    def mock_request(self):
        """Create mock request."""
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.url = "http://test.com/api/test"
        return request

    @pytest.mark.asyncio
    async def test_handle_http_exception(self, mock_request):
        """Test handling of HTTPException."""
        exc = HTTPException(status_code=404, detail="Not found")
        response = await global_exception_handler(mock_request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 404

        import json
        content = json.loads(response.body.decode())
        assert content["error"]["message"] == "Not found"
        assert content["error"]["type"] == "http_exception"

    @pytest.mark.asyncio
    async def test_handle_mcp_error(self, mock_request):
        """Test handling of MCP error."""
        original_error = ConnectionError("Connection lost")
        exc = MCPError("MCP operation failed", original_error)
        response = await global_exception_handler(mock_request, exc)

        assert response.status_code == 500

        import json
        content = json.loads(response.body.decode())
        assert content["error"]["type"] == "mcp_error"
        assert "MCP operation failed" in content["error"]["message"]
        assert content["error"]["details"]["original_error"] == "Connection lost"

    @pytest.mark.asyncio
    async def test_handle_validation_error(self, mock_request):
        """Test handling of validation error."""
        exc = ValidationError("test_field", 123, "Must be a string")
        response = await global_exception_handler(mock_request, exc)

        assert response.status_code == 400

        import json
        content = json.loads(response.body.decode())
        assert content["error"]["type"] == "validation_error"
        assert content["error"]["details"]["field"] == "test_field"
        assert content["error"]["details"]["value"] == "123"

    @pytest.mark.asyncio
    async def test_handle_generic_exception(self, mock_request):
        """Test handling of generic exception."""
        exc = RuntimeError("Unexpected error")
        response = await global_exception_handler(mock_request, exc)

        assert response.status_code == 500

        import json
        content = json.loads(response.body.decode())
        assert content["error"]["type"] == "internal_server_error"
        assert "An unexpected error occurred" in content["error"]["message"]
        assert content["error"]["details"]["exception_type"] == "RuntimeError"


class TestValidationUtilities:
    """Test validation utility functions."""

    def test_validate_graph_payload_success(self):
        """Test successful graph payload validation."""
        payload = {
            "nodes": [
                {"id": "n1", "labels": ["Host"], "attrs": {"ip": "192.168.1.1"}},
                {"id": "n2", "labels": ["Server"], "attrs": {"name": "web-server"}}
            ],
            "edges": [
                {"source": "n1", "target": "n2", "type": "connects_to"}
            ]
        }

        # Should not raise any exception
        validate_graph_payload(payload)

    def test_validate_graph_payload_invalid_type(self):
        """Test validation with invalid payload type."""
        with pytest.raises(ValidationError) as exc_info:
            validate_graph_payload("invalid")

        assert exc_info.value.field == "payload"

    def test_validate_graph_payload_invalid_nodes(self):
        """Test validation with invalid nodes."""
        payload = {"nodes": "not_a_list", "edges": []}

        with pytest.raises(ValidationError) as exc_info:
            validate_graph_payload(payload)

        assert exc_info.value.field == "nodes"

    def test_validate_graph_payload_node_missing_id(self):
        """Test validation with node missing ID."""
        payload = {
            "nodes": [{"labels": ["Host"]}],  # Missing 'id'
            "edges": []
        }

        with pytest.raises(ValidationError) as exc_info:
            validate_graph_payload(payload)

        assert "id" in exc_info.value.field

    def test_validate_graph_payload_invalid_edges(self):
        """Test validation with invalid edges."""
        payload = {"nodes": [], "edges": "not_a_list"}

        with pytest.raises(ValidationError) as exc_info:
            validate_graph_payload(payload)

        assert exc_info.value.field == "edges"

    def test_validate_graph_payload_edge_missing_source(self):
        """Test validation with edge missing source."""
        payload = {
            "nodes": [{"id": "n1"}],
            "edges": [{"target": "n1"}]  # Missing 'source'
        }

        with pytest.raises(ValidationError) as exc_info:
            validate_graph_payload(payload)

        assert "source" in exc_info.value.field

    def test_validate_graph_payload_edge_missing_target(self):
        """Test validation with edge missing target."""
        payload = {
            "nodes": [{"id": "n1"}],
            "edges": [{"source": "n1"}]  # Missing 'target'
        }

        with pytest.raises(ValidationError) as exc_info:
            validate_graph_payload(payload)

        assert "target" in exc_info.value.field

    def test_validate_cypher_query_success(self):
        """Test successful Cypher query validation."""
        queries = [
            "MATCH (n) RETURN n",
            "CREATE (n:Test {name: 'test'})",
            "MATCH (n)-[r]->(m) WHERE n.id = $id RETURN n, r, m"
        ]

        for query in queries:
            validate_cypher_query(query)  # Should not raise

    def test_validate_cypher_query_invalid_type(self):
        """Test validation with non-string query."""
        with pytest.raises(ValidationError) as exc_info:
            validate_cypher_query(123)

        assert exc_info.value.field == "query"

    def test_validate_cypher_query_empty(self):
        """Test validation with empty query."""
        with pytest.raises(ValidationError) as exc_info:
            validate_cypher_query("")

        assert exc_info.value.field == "query"

    def test_validate_cypher_query_whitespace_only(self):
        """Test validation with whitespace-only query."""
        with pytest.raises(ValidationError) as exc_info:
            validate_cypher_query("   \n\t   ")

        assert exc_info.value.field == "query"


class TestErrorHandlingUtilities:
    """Test error handling utility functions."""

    def test_handle_mcp_operation_error_connection(self):
        """Test handling connection-related errors."""
        original_error = Exception("connection timeout occurred")
        result = handle_mcp_operation_error("test_operation", original_error)

        assert isinstance(result, GraphOperationError)
        assert result.operation == "test_operation"
        assert "Failed to connect to Neo4j database" in str(result)

    def test_handle_mcp_operation_error_timeout(self):
        """Test handling timeout errors."""
        original_error = Exception("operation timeout exceeded")
        result = handle_mcp_operation_error("test_operation", original_error)

        assert "Operation timed out" in str(result)

    def test_handle_mcp_operation_error_authentication(self):
        """Test handling authentication errors."""
        original_error = Exception("authentication failed for user")
        result = handle_mcp_operation_error("test_operation", original_error)

        assert "Authentication failed" in str(result)

    def test_handle_mcp_operation_error_cypher(self):
        """Test handling Cypher-related errors."""
        original_error = Exception("cypher syntax error at position 10")
        result = handle_mcp_operation_error("test_operation", original_error)

        assert "Invalid Cypher query" in str(result)

    def test_handle_mcp_operation_error_generic(self):
        """Test handling generic errors."""
        original_error = Exception("Some unexpected error")
        result = handle_mcp_operation_error("test_operation", original_error)

        assert "Some unexpected error" in str(result)

    @pytest.mark.asyncio
    async def test_with_error_handling_success(self):
        """Test successful operation with error handling wrapper."""
        async def test_func():
            return {"result": "success"}

        result = await with_error_handling("test_op", test_func)
        assert result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_with_error_handling_failure(self):
        """Test failed operation with error handling wrapper."""
        async def test_func():
            raise ConnectionError("Connection failed")

        with pytest.raises(GraphOperationError) as exc_info:
            await with_error_handling("test_op", test_func)

        assert exc_info.value.operation == "test_op"
        assert "Failed to connect to Neo4j database" in str(exc_info.value)