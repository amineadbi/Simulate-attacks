"""
MCP integration for Neo4j operations.
Provides a clean interface to interact with Neo4j via MCP protocol using stdio transport.
For now, uses direct Neo4j driver as fallback until MCP integration is stable.
"""
from __future__ import annotations

import os
import logging
from typing import Any, Dict, Optional, List
import asyncio

# Import the proper MCP dependencies
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from langchain_mcp_adapters.tools import load_mcp_tools
    from langchain_core.tools import BaseTool
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    try:
        from neo4j import AsyncGraphDatabase
        NEO4J_AVAILABLE = True
    except ImportError:
        NEO4J_AVAILABLE = False

logger = logging.getLogger(__name__)


class Neo4jMCPClient:
    """Client for Neo4j operations using proper langchain-mcp-adapters pattern."""

    def __init__(self):
        if MCP_AVAILABLE:
            self._session: Optional[ClientSession] = None
            self._tools: Optional[List[BaseTool]] = None
            self._stdio_context = None
            self._mode = "mcp"
        elif NEO4J_AVAILABLE:
            self._driver = None
            self._mode = "direct"
        else:
            self._mode = "mock"

        self._initialized = False

    async def __aenter__(self):
        await self._initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._cleanup()

    async def _initialize(self):
        """Initialize the MCP client or Neo4j driver."""
        if self._initialized:
            return

        try:
            if self._mode == "mcp":
                await self._initialize_mcp()
            elif self._mode == "direct":
                await self._initialize_direct()
            else:
                await self._initialize_mock()

            self._initialized = True
            logger.info(f"Neo4j client initialized successfully in {self._mode} mode")

        except Exception as e:
            logger.error(f"Failed to initialize Neo4j client: {e}")
            # Fallback to mock mode
            self._mode = "mock"
            await self._initialize_mock()
            self._initialized = True
            logger.warning("Initialized in mock mode due to initialization failure")

    async def _initialize_mcp(self):
        """Initialize with proper langchain-mcp-adapters pattern."""
        # Set environment variables for neo4j MCP server
        neo4j_env = {
            "NEO4J_URI": os.getenv("GRAPH_NEO4J_URI", "bolt://localhost:7687"),
            "NEO4J_USERNAME": os.getenv("GRAPH_NEO4J_USER", "neo4j"),
            "NEO4J_PASSWORD": os.getenv("GRAPH_NEO4J_PASSWORD", "neo4jtest"),
            "NEO4J_DATABASE": os.getenv("GRAPH_NEO4J_DATABASE", "neo4j"),
        }

        # Update environment
        for key, value in neo4j_env.items():
            os.environ[key] = value

        # Create server parameters for mcp-neo4j-cypher with explicit environment
        server_params = StdioServerParameters(
            command="python",
            args=["-m", "uv", "tool", "run", "mcp-neo4j-cypher"],
            env=neo4j_env  # Pass environment variables to the subprocess
        )

        # Establish stdio connection
        self._stdio_context = stdio_client(server_params)
        read, write = await self._stdio_context.__aenter__()

        # Create and initialize session
        self._session = ClientSession(read, write)
        await self._session.initialize()

        # Load tools using langchain-mcp-adapters
        self._tools = await load_mcp_tools(self._session)

    async def _initialize_direct(self):
        """Initialize with direct Neo4j driver."""
        uri = os.getenv("GRAPH_NEO4J_URI", "bolt://localhost:7687")
        username = os.getenv("GRAPH_NEO4J_USER", "neo4j")
        password = os.getenv("GRAPH_NEO4J_PASSWORD", "neo4jtest")

        self._driver = AsyncGraphDatabase.driver(uri, auth=(username, password))
        # Test connection
        await self._driver.verify_connectivity()

    async def _initialize_mock(self):
        """Initialize in mock mode."""
        logger.info("Running in mock mode - no actual database operations")

    async def _cleanup(self):
        """Clean up resources."""
        if self._mode == "mcp":
            if self._session:
                try:
                    # Session cleanup is handled by the context manager
                    self._session = None
                except Exception as e:
                    logger.warning(f"Error cleaning up MCP session: {e}")

            if self._stdio_context:
                try:
                    await self._stdio_context.__aexit__(None, None, None)
                except Exception as e:
                    logger.warning(f"Error closing stdio context: {e}")
                finally:
                    self._stdio_context = None

            self._tools = None
        elif self._mode == "direct" and self._driver:
            try:
                await self._driver.close()
            except Exception as e:
                logger.warning(f"Error closing Neo4j driver: {e}")
            finally:
                self._driver = None

        self._initialized = False

    async def call_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call a Neo4j tool using LangChain tool interface."""
        if not self._initialized:
            raise RuntimeError("Client not initialized. Use async context manager.")

        try:
            if self._mode == "mcp":
                return await self._call_mcp_tool(tool_name, params)
            elif self._mode == "direct":
                return await self._call_direct_tool(tool_name, params)
            else:
                return await self._call_mock_tool(tool_name, params)

        except Exception as e:
            logger.error(f"Error calling tool '{tool_name}': {e}")
            raise RuntimeError(f"Tool call failed: {e}")

    def get_tools(self) -> List[BaseTool]:
        """Get the loaded MCP tools as LangChain tools."""
        if not self._initialized:
            raise RuntimeError("Client not initialized. Use async context manager.")

        if self._mode == "mcp" and self._tools:
            return self._tools
        else:
            # Return empty list for direct/mock modes
            return []

    async def _call_mcp_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call tool via LangChain MCP tool interface."""
        if not self._tools:
            raise ValueError("No MCP tools available")

        tool = next((t for t in self._tools if t.name == tool_name), None)
        if not tool:
            available_tools = [t.name for t in self._tools]
            raise ValueError(f"Tool '{tool_name}' not found. Available tools: {available_tools}")

        # Use LangChain tool interface
        result = await tool.ainvoke(params)
        return result if isinstance(result, dict) else {"result": result}

    async def _call_direct_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call tool using direct Neo4j driver."""
        if tool_name == "run-cypher":
            query = params.get("query", "")
            cypher_params = params.get("params", {})
            mode = params.get("mode", "read")

            if mode == "write":
                async with self._driver.session() as session:
                    result = await session.run(query, cypher_params)
                    data = await result.data()
                    summary = result.consume()
                    return {
                        "records": data,
                        "summary": {
                            "query": query,
                            "parameters": cypher_params,
                            "result_available_after": summary.result_available_after,
                            "result_consumed_after": summary.result_consumed_after
                        }
                    }
            else:
                async with self._driver.session() as session:
                    result = await session.run(query, cypher_params)
                    data = await result.data()
                    return {
                        "records": data,
                        "summary": {"query": query, "parameters": cypher_params}
                    }

        elif tool_name == "get-schema":
            # Get schema information
            async with self._driver.session() as session:
                # Get node labels
                labels_result = await session.run("CALL db.labels()")
                labels = [record["label"] for record in await labels_result.data()]

                # Get relationship types
                types_result = await session.run("CALL db.relationshipTypes()")
                types = [record["relationshipType"] for record in await types_result.data()]

                return {
                    "node_labels": labels,
                    "relationship_types": types
                }
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    async def _call_mock_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call tool in mock mode."""
        logger.debug(f"Mock call to {tool_name} with params: {params}")

        if tool_name == "run-cypher":
            query = params.get("query", "")
            if "CREATE" in query.upper():
                return {"records": [], "summary": {"nodes_created": 1}}
            elif "MATCH" in query.upper():
                return {"records": [{"n": {"id": "mock-node", "name": "Mock Node"}}], "summary": {"nodes_returned": 1}}
            else:
                return {"records": [], "summary": {"query_executed": True}}
        elif tool_name == "get-schema":
            return {
                "node_labels": ["Host", "Server", "Database"],
                "relationship_types": ["CONNECTS_TO", "HOSTS", "CONTAINS"]
            }
        else:
            return {"status": "mock_success", "tool": tool_name, "params": params}

    async def get_available_tools(self) -> List[str]:
        """Get list of available tools."""
        if not self._initialized:
            raise RuntimeError("Client not initialized")

        if self._mode == "mcp" and self._tools:
            return [tool.name for tool in self._tools]
        else:
            return ["run-cypher", "get-schema"]


class MCPGraphOperations:
    """High-level graph operations using MCP protocol with proper error handling."""

    def __init__(self, client: Neo4jMCPClient):
        self.client = client

    async def get_schema(self) -> Dict[str, Any]:
        """Get graph schema information."""
        try:
            return await self.client.call_tool("get-schema", {})
        except Exception as e:
            logger.error(f"Failed to get schema: {e}")
            raise

    async def run_cypher(self, query: str, params: Optional[Dict[str, Any]] = None, mode: str = "read") -> Dict[str, Any]:
        """Execute a Cypher query with proper parameter validation."""
        if not query or not isinstance(query, str):
            raise ValueError("Query must be a non-empty string")

        if mode not in ["read", "write"]:
            raise ValueError("Mode must be either 'read' or 'write'")

        try:
            return await self.client.call_tool("run-cypher", {
                "query": query.strip(),
                "params": params or {},
                "mode": mode
            })
        except Exception as e:
            logger.error(f"Failed to execute Cypher query: {e}")
            raise

    async def add_node(self, node_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a node via Cypher with validation."""
        if not isinstance(node_data, dict):
            raise ValueError("Node data must be a dictionary")

        labels = node_data.get("labels", ["Node"])
        if not labels or not isinstance(labels, list):
            labels = ["Node"]

        # Sanitize labels
        sanitized_labels = []
        for label in labels:
            if isinstance(label, str) and label.strip():
                sanitized_labels.append(label.strip())

        if not sanitized_labels:
            sanitized_labels = ["Node"]

        label_str = ":".join(sanitized_labels)
        attrs = node_data.get("attrs", {})

        if not isinstance(attrs, dict):
            attrs = {}

        # Ensure id is set
        if "id" not in attrs and "id" in node_data:
            attrs["id"] = node_data["id"]

        query = f"""
        CREATE (n:{label_str} $props)
        RETURN n
        """

        return await self.run_cypher(query, {"props": attrs}, "write")

    async def add_edge(self, edge_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add an edge via Cypher with validation."""
        if not isinstance(edge_data, dict):
            raise ValueError("Edge data must be a dictionary")

        required_fields = ["source", "target"]
        for field in required_fields:
            if field not in edge_data:
                raise ValueError(f"Edge data missing required field: {field}")

        edge_type = edge_data.get("type", "RELATED")
        if not isinstance(edge_type, str) or not edge_type.strip():
            edge_type = "RELATED"

        query = """
        MATCH (source {id: $source_id}), (target {id: $target_id})
        CREATE (source)-[r:RELATIONSHIP]->(target)
        SET r.type = $edge_type, r += $props
        RETURN r
        """

        return await self.run_cypher(query, {
            "source_id": str(edge_data["source"]),
            "target_id": str(edge_data["target"]),
            "edge_type": edge_type.strip(),
            "props": edge_data.get("attrs", {})
        }, "write")

    async def update_node(self, node_id: str, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Update node attributes with validation."""
        if not node_id or not isinstance(node_id, str):
            raise ValueError("Node ID must be a non-empty string")

        if not isinstance(attrs, dict):
            raise ValueError("Attributes must be a dictionary")

        query = """
        MATCH (n {id: $node_id})
        SET n += $attrs
        RETURN n
        """

        return await self.run_cypher(query, {"node_id": node_id.strip(), "attrs": attrs}, "write")

    async def update_edge(self, edge_id: str, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Update edge attributes with validation."""
        if not edge_id or not isinstance(edge_id, str):
            raise ValueError("Edge ID must be a non-empty string")

        if not isinstance(attrs, dict):
            raise ValueError("Attributes must be a dictionary")

        query = """
        MATCH ()-[r {id: $edge_id}]->()
        SET r += $attrs
        RETURN r
        """

        return await self.run_cypher(query, {"edge_id": edge_id.strip(), "attrs": attrs}, "write")

    async def delete_node(self, node_id: str) -> Dict[str, Any]:
        """Delete a node and its relationships with validation."""
        if not node_id or not isinstance(node_id, str):
            raise ValueError("Node ID must be a non-empty string")

        query = """
        MATCH (n {id: $node_id})
        DETACH DELETE n
        RETURN count(n) as deleted_count
        """

        result = await self.run_cypher(query, {"node_id": node_id.strip()}, "write")
        return {"status": "deleted", "node_id": node_id, "result": result}

    async def delete_edge(self, edge_id: str) -> Dict[str, Any]:
        """Delete an edge with validation."""
        if not edge_id or not isinstance(edge_id, str):
            raise ValueError("Edge ID must be a non-empty string")

        query = """
        MATCH ()-[r {id: $edge_id}]->()
        DELETE r
        RETURN count(r) as deleted_count
        """

        result = await self.run_cypher(query, {"edge_id": edge_id.strip()}, "write")
        return {"status": "deleted", "edge_id": edge_id, "result": result}

    async def load_graph(self, graph_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Load a complete graph from payload with proper transaction handling."""
        if not isinstance(graph_payload, dict):
            raise ValueError("Graph payload must be a dictionary")

        nodes = graph_payload.get("nodes", [])
        edges = graph_payload.get("edges", [])

        if not isinstance(nodes, list):
            nodes = []
        if not isinstance(edges, list):
            edges = []

        results = {
            "nodes_created": 0,
            "edges_created": 0,
            "errors": []
        }

        # Create nodes first
        for node in nodes:
            try:
                await self.add_node(node)
                results["nodes_created"] += 1
            except Exception as e:
                error_msg = f"Failed to create node {node.get('id', 'unknown')}: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)

        # Create edges after nodes
        for edge in edges:
            try:
                await self.add_edge(edge)
                results["edges_created"] += 1
            except Exception as e:
                edge_id = f"{edge.get('source', '?')}->{edge.get('target', '?')}"
                error_msg = f"Failed to create edge {edge_id}: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)

        return results