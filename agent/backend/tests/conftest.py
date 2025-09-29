"""
Pytest configuration and fixtures for backend tests.
"""
import pytest
import asyncio
from unittest.mock import patch


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing."""
    env_vars = {
        "GRAPH_NEO4J_URI": "bolt://localhost:7687",
        "GRAPH_NEO4J_USER": "neo4j",
        "GRAPH_NEO4J_PASSWORD": "testpass",
        "GRAPH_NEO4J_DATABASE": "neo4j",
        "OPENAI_API_KEY": "test-key",
        "OPENAI_MODEL": "gpt-4o-mini"
    }

    with patch.dict("os.environ", env_vars):
        yield env_vars


@pytest.fixture
def disable_mcp_initialization():
    """Disable actual MCP initialization for unit tests."""
    with patch('agent.mcp_integration.MCPToolkit') as mock_toolkit:
        mock_toolkit.return_value = None
        yield mock_toolkit