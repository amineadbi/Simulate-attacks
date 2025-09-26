from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langgraph.graph import END, StateGraph

from .config import AgentConfig, load_config
from .llm import build_llm
from .nodes import cypher as cypher_node
from .nodes import graph_tools, intent_classifier, router as router_node
from .nodes import respond as respond_node
from .nodes import result_ingest
from .nodes import scenario_planner
from .state import AgentState, AgentStateAnnotations
from .tools import ToolRegistry


class AgentApplication:
    def __init__(self, graph, tools: ToolRegistry, config: AgentConfig, system_message: Optional[SystemMessage]):
        self.graph = graph
        self.tools = tools
        self.config = config
        self.system_message = system_message

    async def aclose(self) -> None:
        await self.tools.aclose()


def _load_system_message(path: Path) -> Optional[SystemMessage]:
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return None
    return SystemMessage(content=content)


def create_application(config: Optional[AgentConfig] = None, *, llm: Optional[BaseChatModel] = None):
    cfg = config or load_config()
    llm_model = llm or build_llm(cfg)
    tools = ToolRegistry.from_config(cfg.tools)
    system_message = _load_system_message(cfg.system_prompt_path)

    builder = StateGraph(AgentState, annotations=AgentStateAnnotations)

    builder.add_node("classify_intent", partial(intent_classifier.classify_intent, llm=llm_model))
    builder.add_node("plan_graph_action", partial(graph_tools.plan_graph_action, llm=llm_model))
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
            "plan_scenario": "plan_scenario",
            "monitor_job": "monitor_job",
            "run_cypher": "run_cypher",
            "summarise_job": "summarise_job",
            "respond": "respond",
        },
    )

    builder.add_edge("plan_graph_action", "execute_graph_action")
    builder.add_edge("execute_graph_action", "respond")

    builder.add_edge("plan_scenario", "execute_scenario")
    builder.add_edge("execute_scenario", "monitor_job")
    builder.add_edge("monitor_job", "respond")

    builder.add_edge("run_cypher", "respond")
    builder.add_edge("summarise_job", "respond")

    builder.add_edge("respond", END)

    graph = builder.compile()

    return AgentApplication(graph=graph, tools=tools, config=cfg, system_message=system_message)
