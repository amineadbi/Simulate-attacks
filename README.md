# Sentinel Guide Agent

LangGraph-based conversational orchestrator that drives the network-graph MCP tools and breach-and-attack simulation connectors described in lueprint.txt.

## Layout

- gent/
  - config.py – lightweight configuration loader for model + MCP endpoints.
  - low.py – builds the LangGraph wiring the intent classifier, graph tools, scenario planner, and responder.
  - llm.py – helper to instantiate the chat model (uses OpenAI via langchain-openai).
  - models.py – pydantic models shared across nodes.
  - state.py – LangGraph state definition + aggregation rules.
  - 	ools.py – async MCP client + registry.
  - 
odes/ – atomic LangGraph nodes (intent classifier, graph ops, scenario execution, Cypher, response drafting).
  - prompts/system.md – system persona instructions.

## Quickstart

1. Create and activate a Python 3.10+ virtualenv.
2. pip install -e . to pull LangGraph/LangChain deps.
3. Set environment variables:
   - OPENAI_API_KEY (or swap llm.py to your provider).
   - OPENAI_MODEL (defaults to gpt-4.1).
   - MCP_TOOLS comma list like graph:https://localhost:8000/tools,caldera:https://localhost:9001/tools.
   - Optional per-tool API keys (MCP_GRAPH_API_KEY, etc.).
4. Use gent.flow.create_application() to produce the compiled graph.  Example:

`python
import asyncio
from agent.flow import create_application

async def main():
    app = create_application()
    state = {
        "messages": [
            {"type": "human", "content": "Load the latest BNP subnet JSON."}
        ]
    }
    async for event in app.graph.astream(state):
        print(event)
    await app.aclose()

asyncio.run(main())
`

Adapt the state["messages"] structure to LangChain message objects when wiring into your chat runtime (e.g., LangServe, FastAPI endpoint, etc.).

## Next Steps

- Hook gent.flow.create_application into your orchestrator runner (e.g., LangServe or custom FastAPI endpoint).
- Implement confirmation loops for destructive graph mutations (wire graph_plan_confirmed).
- Extend ToolRegistry with health checks + caching if multiple tools share base URLs.
- Add evaluation traces (see blueprint §12) via scripted conversations.
- Layer in unit tests (	ests/) covering planners + routing once tool mocks exist.
