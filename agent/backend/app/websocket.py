from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect


class WebSocketErrorType(str, Enum):
    """Enumeration of WebSocket error types for structured error handling."""
    JSON_DECODE = "json_decode_error"
    AGENT_INITIALIZATION = "agent_initialization_error"
    AGENT_EXECUTION = "agent_execution_error"
    MESSAGE_VALIDATION = "message_validation_error"
    INTERNAL_ERROR = "internal_error"
    CONNECTION_ERROR = "connection_error"
try:
    from langchain_core.messages import HumanMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    LANGCHAIN_AVAILABLE = False

    class HumanMessage:  # type: ignore
        def __init__(self, content: str):
            self.content = content

try:
    from ...flow import create_application
    FLOW_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    FLOW_AVAILABLE = False
    create_application = None  # type: ignore

from .events import get_broker, EventBroker
from ...mcp_integration import Neo4jMCPClient

router = APIRouter()
logger = logging.getLogger(__name__)

if not LANGCHAIN_AVAILABLE:
    logger.warning("langchain_core not available; using simple HumanMessage stub")


def get_agent_app_from_state(websocket: WebSocket):
    """Get agent application from FastAPI app state."""
    if not hasattr(websocket.app.state, 'agent_app'):
        logger.warning("Agent app not initialized in app state")
        return None
    return websocket.app.state.agent_app


async def send_error_message(
    websocket: WebSocket,
    error_type: WebSocketErrorType,
    message: str,
    recoverable: bool = True,
    retry_after_ms: Optional[int] = None
) -> None:
    """Send structured error message to client with reconnection metadata."""
    error_payload = {
        "type": "error",
        "payload": {
            "error_type": error_type.value,
            "message": message,
            "recoverable": recoverable,
            "timestamp": datetime.now().isoformat()
        }
    }

    if retry_after_ms is not None:
        error_payload["payload"]["retry_after_ms"] = retry_after_ms

    try:
        await websocket.send_text(json.dumps(error_payload))
    except Exception as e:
        logger.error(f"Failed to send error message: {e}")


async def handle_agent_message(websocket: WebSocket, message: Dict[str, Any], broker: EventBroker):
    """Handle agent chat messages and invoke LangGraph agent."""
    message_type = message.get("type")
    command = message.get("command")
    payload = message.get("payload", {})

    if message_type == "agent.command" and command == "chat":
        # Extract user message from the chat command
        user_message = payload.get("text", "").strip()
    elif message_type == "agent.message":
        # Extract user message from agent.message type
        user_message = payload.get("message", "").strip()
    else:
        user_message = None

    if user_message:
        logger.info(f"Processing user message: '{user_message}' (type: {message_type}, command: {command})")

        # Send acknowledgment
        await websocket.send_text(json.dumps({
            "id": f"log-{int(datetime.now().timestamp() * 1000)}",
            "type": "agent.log",
            "createdAt": datetime.now().isoformat(),
            "payload": {
                "message": f"Processing: {user_message}"
            },
            "level": "info"
        }))

        # Try to invoke the real LangGraph agent
        try:
            logger.info("Getting agent application from app state...")
            agent_app = get_agent_app_from_state(websocket)
            if agent_app and agent_app.graph:
                logger.info("Agent available, invoking LangGraph...")

                configurable: Dict[str, Any] = {}

                thread_id = payload.get("thread_id") or getattr(websocket.state, "thread_id", None)
                if not thread_id:
                    thread_id = getattr(websocket.state, "connection_id", None)
                if not thread_id:
                    thread_id = uuid.uuid4().hex
                websocket.state.thread_id = thread_id
                configurable["thread_id"] = thread_id

                checkpoint_ns = payload.get("checkpoint_ns") or getattr(websocket.state, "checkpoint_ns", None)
                if checkpoint_ns:
                    configurable["checkpoint_ns"] = checkpoint_ns
                    websocket.state.checkpoint_ns = checkpoint_ns

                checkpoint_id = payload.get("checkpoint_id")
                if checkpoint_id:
                    configurable["checkpoint_id"] = checkpoint_id

                graph_config = {"configurable": configurable}

                logger.info(f"Using LangGraph config: {graph_config}")

                # Create a proper agent state with the user message
                agent_input = {
                    "messages": [HumanMessage(content=user_message)]
                }
                logger.info(f"Agent input prepared: {agent_input}")

                # Invoke the agent with streaming to capture each node execution
                logger.info("Invoking agent.graph.astream...")
                print("Starting LangGraph execution with streaming...")

                # Stream events to see each node execution
                final_result = None
                async for event in agent_app.graph.astream(agent_input, config=graph_config):
                    node_name = list(event.keys())[0] if event else "unknown"
                    print(f"LangGraph Node: {node_name}")
                    logger.info(f"Executing node: {node_name}")
                    logger.debug(f"   Node output: {event}")
                    final_result = event

                # Get the final state
                result = final_result if final_result else {}
                logger.info(f"Agent execution completed. Result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")
                print(f"LangGraph execution completed")

                # Extract the response from the agent result
                if "messages" in result and result["messages"]:
                    last_message = result["messages"][-1]
                    response = last_message.content if hasattr(last_message, 'content') else str(last_message)
                    logger.info(f"Agent response extracted: {response[:100]}...")
                else:
                    response = "Agent completed processing but no response was generated."
                    logger.warning("No messages in agent result")

                logger.info("Sending agent response to WebSocket")
            else:
                # Fallback to enhanced mock response if agent creation failed
                logger.warning("Using mock response - agent not available")
                response = await generate_agent_response(user_message)

        except Exception as e:
            logger.error(f"Error invoking agent: {e}", exc_info=True)
            # Send structured error with retry guidance
            await send_error_message(
                websocket,
                WebSocketErrorType.AGENT_EXECUTION,
                f"Agent execution failed: {str(e)}",
                recoverable=True,
                retry_after_ms=1000
            )
            # Fallback to mock response
            response = await generate_agent_response(user_message)

        # Send agent response
        await websocket.send_text(json.dumps({
            "id": f"msg-{int(datetime.now().timestamp() * 1000)}",
            "type": "agent.message",
            "createdAt": datetime.now().isoformat(),
            "payload": {
                "role": "assistant",
                "content": response
            }
        }))

    elif message_type == "graph.request":
        # Handle graph data requests
        await websocket.send_text(json.dumps({
            "type": "graph.data",
            "payload": {
                "nodes": [],
                "edges": []
            }
        }))

    else:
        # Handle empty user message or unknown message types
        if not user_message and message_type in ["agent.command", "agent.message"]:
            await websocket.send_text(json.dumps({
                "type": "agent.log",
                "payload": {
                    "message": "Please provide a message to process",
                    "level": "warning"
                }
            }))
        else:
            # Unknown message type
            await websocket.send_text(json.dumps({
                "type": "agent.log",
                "payload": {
                    "message": f"Unknown message type: {message_type} (command: {command})",
                    "level": "warning"
                }
            }))


async def generate_agent_response(user_message: str) -> str:
    """Generate a mock agent response based on user input."""
    message_lower = user_message.lower()

    if any(word in message_lower for word in ["simulation", "attack", "scenario"]):
        return (
            "I can help you run attack simulations! Here are some options:\n\n"
            "- **Lateral Movement**: Simulate attacker movement between systems\n"
            "- **Privilege Escalation**: Test elevation of privileges\n"
            "- **Data Exfiltration**: Analyze data theft scenarios\n"
            "- **Persistence**: Evaluate long-term access methods\n\n"
            "To start a simulation, try: 'Run a lateral movement simulation'"
        )

    elif any(word in message_lower for word in ["graph", "topology", "network"]):
        return (
            "I can analyze your network topology! To get started:\n\n"
            "1. **Upload a graph**: Use the 'Upload Graph JSON' button\n"
            "2. **Load sample data**: Click 'Load Sample Graph' for a demo\n"
            "3. **Run queries**: Use the Cypher panel to explore your data\n\n"
            "Try loading the sample graph to see a network visualization."
        )

    elif any(word in message_lower for word in ["cypher", "query", "search"]):
        return (
            "You can use Cypher queries to explore your graph data:\n\n"
            "**Common queries:**\n"
            "```\n"
            "MATCH (n) RETURN n LIMIT 10\n"
            "MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 5\n"
            "```\n\n"
            "The query results will appear below the Cypher panel."
        )

    elif any(word in message_lower for word in ["help", "how", "what", "?"]):
        return (
            "Welcome to the **Graph Scenario Workbench**!\n\n"
            "**What I can help with:**\n"
            "- **Graph analysis** - upload and visualize network topologies\n"
            "- **Attack simulations** - run cybersecurity scenarios\n"
            "- **Cypher queries** - explore graph data with Neo4j queries\n"
            "- **Real-time monitoring** - track simulation progress\n\n"
            "**Quick start:** Try 'Load sample graph' to see the visualization!"
        )
    else:
        return (
            f"I understand you're asking about: *{user_message}*\n\n"
            "I'm a cybersecurity agent focused on graph analysis and attack simulations. "
            "For best results, try queries about:\n"
            "- Network topology analysis\n"
            "- Attack scenario planning\n"
            "- Graph data exploration\n\n"
            "Type 'help' for more information!"
        )


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    logger.info("WebSocket endpoint hit")
    print("WebSocket endpoint hit")

    broker = get_broker()
    connection = None

    try:
        logger.info("Accepting WebSocket connection...")
        await websocket.accept()
        logger.info("WebSocket accepted, registering with broker...")
        connection = await broker.register(websocket)
        websocket.state.connection = connection
        websocket.state.connection_id = connection.id
        if not getattr(websocket.state, 'thread_id', None):
            websocket.state.thread_id = connection.id

        # Agent app is already initialized in app.state by lifespan
        logger.info("WebSocket connected - agent app available from app.state")

        logger.info("Entering WebSocket message loop")
        while True:
            try:
                # Keep the connection alive by waiting for messages
                logger.info("Waiting for WebSocket message...")
                data = await websocket.receive_text()
                logger.info(f"WebSocket received message: {data[:200]}...")

                # Parse and handle agent messages
                try:
                    message = json.loads(data)
                    logger.info(f"Parsed WebSocket message: type={message.get('type')}, command={message.get('command')}")
                    await handle_agent_message(websocket, message, broker)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                    await send_error_message(
                        websocket,
                        WebSocketErrorType.JSON_DECODE,
                        "Invalid JSON format in message",
                        recoverable=True
                    )
            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected normally")
                break
            except Exception as e:
                logger.error(f"WebSocket error during receive: {e}", exc_info=True)
                # Send structured error with reconnection hint
                await send_error_message(
                    websocket,
                    WebSocketErrorType.INTERNAL_ERROR,
                    f"Internal server error: {str(e)}",
                    recoverable=True,
                    retry_after_ms=5000  # Suggest reconnect after 5 seconds
                )
                break

    except Exception as e:
        logger.error(f"WebSocket connection error: {e}", exc_info=True)
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass
    finally:
        if connection:
            try:
                await broker.unregister(connection)
            except Exception as e:
                logger.error(f"Error unregistering WebSocket connection: {e}")
