from __future__ import annotations

import logging
from functools import partial
from pathlib import Path
from typing import Optional, List

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import create_react_agent

from .config import AgentConfig, load_config
from .llm import build_llm
from .mcp_integration import Neo4jMCPClient
from .nodes import cypher as cypher_node
from .nodes import graph_tools, intent_classifier, router as router_node
from .nodes import respond as respond_node
from .nodes import result_ingest
from .nodes import scenario_planner
from .state import AgentState, AgentStateAnnotations
from .tools import ToolRegistry

logger = logging.getLogger(__name__)


class AgentApplication:
    def __init__(self, graph, tools: ToolRegistry, config: AgentConfig, system_message: Optional[SystemMessage], mcp_tools: Optional[List[BaseTool]] = None):
        self.graph = graph
        self.tools = tools
        self.config = config
        self.system_message = system_message
        self.mcp_tools = mcp_tools or []
        self._mcp_client: Optional[Neo4jMCPClient] = None

    async def get_mcp_client(self) -> Neo4jMCPClient:
        """Get or create MCP client for direct tool access."""
        if not self._mcp_client:
            self._mcp_client = Neo4jMCPClient()
        return self._mcp_client

    async def aclose(self) -> None:
        await self.tools.aclose()
        if self._mcp_client:
            await self._mcp_client.__aexit__(None, None, None)


def _load_system_message(path: Path) -> Optional[SystemMessage]:
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return None
    return SystemMessage(content=content)


async def create_application(config: Optional[AgentConfig] = None, *, llm: Optional[BaseChatModel] = None):
    """Create the agent application with MCP tools integration."""
    cfg = config or load_config()
    llm_model = llm or build_llm(cfg)
    tools = ToolRegistry.create_minimal()  # Use minimal registry, MCP tools loaded separately
    system_message = _load_system_message(cfg.system_prompt_path)

    # Load MCP tools
    mcp_tools = []
    logger.info("Starting MCP tools initialization...")
    try:
        mcp_client = Neo4jMCPClient()
        logger.info("Created Neo4j MCP client")
        async with mcp_client:
            logger.info("MCP client context entered, loading tools...")
            mcp_tools = mcp_client.get_tools()
            logger.info(f"✅ Successfully loaded {len(mcp_tools)} MCP tools: {[t.name for t in mcp_tools]}")
    except Exception as e:
        logger.error(f"❌ Failed to load MCP tools: {e}", exc_info=True)

    # Create custom LangGraph with both traditional nodes and MCP tools
    logger.info("Building LangGraph state graph...")
    builder = StateGraph(AgentState, annotations=AgentStateAnnotations)

    builder.add_node("classify_intent", partial(intent_classifier.classify_intent, llm=llm_model))
    builder.add_node("plan_graph_action", partial(graph_tools.plan_graph_action, llm=llm_model))
    builder.add_node("confirm_graph_action", graph_tools.confirm_graph_action)
    builder.add_node("reject_graph_action", graph_tools.reject_graph_action)
    builder.add_node("execute_graph_action", partial(graph_tools.execute_graph_action, tools=tools))
    builder.add_node("plan_scenario", partial(scenario_planner.plan_scenario, llm=llm_model))
    builder.add_node("execute_scenario", partial(scenario_planner.execute_scenario, tools=tools))
    builder.add_node("monitor_job", partial(scenario_planner.monitor_job, tools=tools))
    builder.add_node("run_cypher", partial(cypher_node.run_cypher, llm=llm_model, tools=tools))
    builder.add_node("summarise_job", partial(result_ingest.summarise_job, llm=llm_model, tools=tools))
    builder.add_node("respond", partial(respond_node.respond, llm=llm_model))

    builder.set_entry_point("classify_intent")

    builder.add_conditional_edges(
        "classify_intent",
        router_node.route,
        {
            "plan_graph_action": "plan_graph_action",
            "confirm_graph_action": "confirm_graph_action",
            "reject_graph_action": "reject_graph_action",
            "plan_scenario": "plan_scenario",
            "monitor_job": "monitor_job",
            "run_cypher": "run_cypher",
            "summarise_job": "summarise_job",
            "respond": "respond",
        },
    )

    builder.add_edge("plan_graph_action", "execute_graph_action")
    builder.add_edge("confirm_graph_action", "execute_graph_action")
    builder.add_edge("reject_graph_action", "respond")
    builder.add_edge("execute_graph_action", "respond")

    builder.add_edge("plan_scenario", "execute_scenario")
    builder.add_edge("execute_scenario", "monitor_job")
    builder.add_edge("monitor_job", "respond")

    builder.add_edge("run_cypher", "respond")
    builder.add_edge("summarise_job", "respond")

    builder.add_edge("respond", END)

    logger.info("Compiling LangGraph...")
    graph = builder.compile()
    logger.info("✅ LangGraph compiled successfully")

    app = AgentApplication(graph=graph, tools=tools, config=cfg, system_message=system_message, mcp_tools=mcp_tools)
    logger.info("✅ AgentApplication created successfully")
    return app


def create_simple_react_agent(config: Optional[AgentConfig] = None, *, llm: Optional[BaseChatModel] = None, mcp_tools: Optional[List[BaseTool]] = None):
    """Create a simple React agent with MCP tools for basic chat functionality."""
    cfg = config or load_config()
    llm_model = llm or build_llm(cfg)
    system_message = _load_system_message(cfg.system_prompt_path)

    # Create a React agent with MCP tools
    tools_list = mcp_tools or []

    # Add system message if available
    system_prompt = system_message.content if system_message else "You are a helpful cybersecurity assistant that can analyze network graphs and run simulations."

    # Create the React agent
    agent = create_react_agent(llm_model, tools_list, messages_modifier=system_prompt)

    return agent
