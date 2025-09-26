# Sentinel Guide Agent

Sentinel Guide is a LangGraph-based conversational orchestrator that drives the network-graph MCP tools and breach-and-attack simulation connectors outlined in lueprint.txt. During this session we stood up the initial agent skeleton: the gent package with typed models and configuration, an async MCP tool registry, LangGraph nodes for graph mutations, Cypher querying, scenario execution, and result summarisation, and the create_application flow that binds everything together. This document captures the current structure, setup steps, and immediate follow-ups.

## Project Layout

- gent/
  - config.py – configuration loader for LLM model selection and MCP endpoints.
  - low.py – compiles the LangGraph with intent classification, graph tooling, scenario planning, monitoring, and response nodes.
  - llm.py – helper for instantiating the chat model (defaults to langchain-openai).
  - models.py – Pydantic contracts for graph payloads, mutations, scenarios, and tool call telemetry.
  - state.py – LangGraph state definition plus helper to merge contextual data.
  - 	ools.py – async MCP client + registry abstraction.
  - 
odes/ – atomic LangGraph nodes (intent classifier, graph planner/executor, scenario planner, Cypher runner, result summariser, responder).
  - prompts/system.md – Sentinel Guide system persona.
- pyproject.toml – dependency metadata for LangGraph/LangChain stack.
- README.md – you are here.

## Quickstart

1. Create and activate a Python =3.10 virtual environment.
2. Install dependencies locally: pip install -e .
3. Export environment variables:
   - OPENAI_API_KEY (or adapt llm.py to your provider).
   - OPENAI_MODEL (defaults to gpt-4.1).
   - MCP_TOOLS comma-separated list, e.g. graph:https://localhost:8000/tools,caldera:https://localhost:9001/tools.
   - Optional per-tool secrets such as MCP_GRAPH_API_KEY.
4. Create the application and stream a conversation:

`python
import asyncio
from agent.flow import create_application
from langchain_core.messages import HumanMessage

async def main():
    app = create_application()
    state = {"messages": [HumanMessage(content="Load the latest BNP subnet JSON.")]}
    async for event in app.graph.astream(state):
        print(event)
    await app.aclose()

asyncio.run(main())
`

Adapt the state["messages"] list to the message objects emitted by your chat runtime (LangServe, FastAPI endpoint, etc.).

## Current Capabilities

- Intent classifier labels new turns and routes the LangGraph to graph mutation, scenario planning, Cypher, or response paths.
- Graph planner produces MCP tool calls with confirmation support; executor records mutation history and tool telemetry.
- Scenario planner queues BAS jobs via configured connectors, monitors status, and summarises findings back into the conversation.
- Cypher node drafts guarded queries (read/write) and relays row counts; responder synthesises concise follow-ups referencing recent tool activity.

## Next Steps

- Surface and enforce confirmation loops for destructive graph mutations (graph_plan_confirmed).
- Add mocked MCP/Caldera clients plus LangGraph unit tests to exercise every branch.
- Integrate the agent flow with the broader conversational entrypoint (streaming, persistence, auth) and extend telemetry/RBAC as needed.
