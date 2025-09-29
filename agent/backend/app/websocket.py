from __future__ import annotations

import json
import logging
from typing import Dict, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage

from .events import get_broker, EventBroker
from ...flow import create_application
from ...mcp_integration import Neo4jMCPClient

router = APIRouter()
logger = logging.getLogger(__name__)

# Global agent instance
_agent_app = None


async def get_agent_app():
    """Get or create the agent application."""
    global _agent_app
    if _agent_app is None:
        try:
            logger.info("🚀 Starting agent application creation...")
            _agent_app = await create_application()
            logger.info("✅ Agent application created successfully")
        except Exception as e:
            logger.error(f"❌ Failed to create agent application: {e}", exc_info=True)
            # Fallback to None, will use mock responses
            _agent_app = None
    else:
        logger.debug("♻️ Reusing existing agent application")
    return _agent_app


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
        logger.info(f"📨 Processing user message: '{user_message}' (type: {message_type}, command: {command})")

        # Send acknowledgment
        await websocket.send_text(json.dumps({
            "type": "agent.log",
            "payload": {
                "message": f"Processing: {user_message}",
                "level": "info"
            }
        }))

        # Try to invoke the real LangGraph agent
        try:
            logger.info("🔄 Getting agent application...")
            agent_app = await get_agent_app()
            if agent_app and agent_app.graph:
                logger.info("🤖 Agent available, invoking LangGraph...")
                # Create a proper agent state with the user message
                agent_input = {
                    "messages": [HumanMessage(content=user_message)]
                }
                logger.info(f"📝 Agent input prepared: {agent_input}")

                # Invoke the agent
                logger.info("🚀 Invoking agent.graph.ainvoke...")
                result = await agent_app.graph.ainvoke(agent_input)
                logger.info(f"✅ Agent execution completed. Result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")

                # Extract the response from the agent result
                if "messages" in result and result["messages"]:
                    last_message = result["messages"][-1]
                    response = last_message.content if hasattr(last_message, 'content') else str(last_message)
                    logger.info(f"💬 Agent response extracted: {response[:100]}...")
                else:
                    response = "Agent completed processing but no response was generated."
                    logger.warning("⚠️ No messages in agent result")

                logger.info(f"📤 Sending agent response to WebSocket")
            else:
                # Fallback to enhanced mock response if agent creation failed
                logger.warning("Using mock response - agent not available")
                response = await generate_agent_response(user_message)

        except Exception as e:
            logger.error(f"Error invoking agent: {e}")
            # Fallback to mock response on error
            response = await generate_agent_response(user_message)
            # Also send error log
            await websocket.send_text(json.dumps({
                "type": "agent.log",
                "payload": {
                    "message": f"Agent error (using fallback): {str(e)}",
                    "level": "warning"
                }
            }))

        # Send agent response
        await websocket.send_text(json.dumps({
            "type": "agent.response",
            "payload": {
                "message": response,
                "timestamp": "2025-09-29T12:00:00Z"
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
            "• **Lateral Movement**: Simulate attacker movement between systems\n"
            "• **Privilege Escalation**: Test elevation of privileges\n"
            "• **Data Exfiltration**: Analyze data theft scenarios\n"
            "• **Persistence**: Evaluate long-term access methods\n\n"
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
            "Welcome to the **Graph Scenario Workbench**! 🎯\n\n"
            "**What I can help with:**\n"
            "• 📊 **Graph Analysis** - Upload and visualize network topologies\n"
            "• 🎭 **Attack Simulations** - Run cybersecurity scenarios\n"
            "• 🔍 **Cypher Queries** - Explore graph data with Neo4j queries\n"
            "• 📈 **Real-time Monitoring** - Track simulation progress\n\n"
            "**Quick start:** Try 'Load sample graph' to see the visualization!"
        )

    else:
        return (
            f"I understand you're asking about: *{user_message}*\n\n"
            "I'm a cybersecurity agent focused on graph analysis and attack simulations. "
            "For best results, try queries about:\n"
            "• Network topology analysis\n"
            "• Attack scenario planning\n"
            "• Graph data exploration\n\n"
            "Type 'help' for more information!"
        )


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    print("🚨 WEBSOCKET ENDPOINT HIT!")  # Basic print to ensure it's called
    logger.info("🚨 WEBSOCKET ENDPOINT HIT!")

    broker = get_broker()
    connection = None

    try:
        logger.info("🤝 Accepting WebSocket connection...")
        await websocket.accept()
        logger.info("✅ WebSocket accepted, registering with broker...")
        connection = await broker.register(websocket)

        # Initialize agent on first connection
        logger.info("🔌 WebSocket connected - initializing agent")
        try:
            agent_result = await get_agent_app()
            if agent_result:
                logger.info("✅ Agent successfully initialized on WebSocket connection")
            else:
                logger.error("❌ Agent initialization returned None")
        except Exception as e:
            logger.error(f"❌ Agent initialization failed: {e}", exc_info=True)

        while True:
            try:
                # Keep the connection alive by waiting for messages
                logger.info("🔄 Waiting for WebSocket message...")
                data = await websocket.receive_text()
                logger.info(f"📥 WebSocket received message: {data[:200]}...")

                # Parse and handle agent messages
                try:
                    message = json.loads(data)
                    logger.info(f"📥 Parsed WebSocket message: type={message.get('type')}, command={message.get('command')}")
                    await handle_agent_message(websocket, message, broker)
                except json.JSONDecodeError as e:
                    logger.error(f"❌ JSON decode error: {e}")
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "payload": {"message": "Invalid JSON format"}
                    }))
            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected normally")
                break
            except Exception as e:
                logger.error(f"WebSocket error during receive: {e}")
                # Send error message to client if possible
                try:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "payload": {"message": f"WebSocket error: {str(e)}"}
                    }))
                except:
                    pass
                break

    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
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