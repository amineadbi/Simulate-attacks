# Graph Scenario Workbench

An end-to-end laboratory for experimenting with defensive network scenarios on graph data. The workspace stitches together a LangGraph-driven agent, a FastAPI orchestration tier, a Vite/React workbench, and a simulation harness so analysts can ingest topologies, reason about them conversationally, and rehearse attack playbooks from one pane of glass.

## Table of contents

1. [System architecture](#system-architecture)
2. [Component responsibilities](#component-responsibilities)
3. [Data flow overview](#data-flow-overview)
4. [Getting started](#getting-started)
5. [Configuration reference](#configuration-reference)
6. [Operating the workbench](#operating-the-workbench)
7. [Developer workflow](#developer-workflow)
8. [Repository layout](#repository-layout)
9. [Roadmap & current focus](#roadmap--current-focus)

## System architecture

```mermaid
flowchart TD
    subgraph UI[React/Vite Workbench]
        ChatPanel[[Chat Panel]]
        GraphCanvas[[Graph Canvas (Sigma.js)]]
        ScenarioDrawer[[Scenario Controls]]
    end

    subgraph API[FastAPI Orchestrator]
        REST[/REST /tools endpoints/]
        WS[/WebSocket /ws stream/]
        Broker[(Event Broker)]
    end

    subgraph Agent[LangGraph Agent Runtime]
        IntentRouter[[Intent Router]]
        GraphTools[[Graph Tooling Nodes]]
        ScenarioPlanner[[Scenario Planner]]
    end

    subgraph MCP[MCP + Graph Store]
        Neo4jMCP[[mcp-neo4j-cypher]]
        Neo4j[(Neo4j / Memgraph)]
    end

    subgraph Sim[Simulation Engine]
        MockAdapter[[Mock Platform Adapter]]
        FutureAdapters[[Caldera / BAS Connectors]]
    end

    UI -- fetch/load_graph, run_cypher --> REST
    UI <-- graph.data, agent.response --> WS
    WS <--> Broker
    Broker --> Agent
    Agent --> MCP
    Neo4jMCP <--> Neo4j
    Agent --> Sim
    Sim --> Broker
```

## Component responsibilities

| Area | What lives there | Highlights |
| --- | --- | --- |
| `agent/flow.py`, `agent/state.py` | LangGraph assembly & shared state | Intent routing, confirmation gates, transcript tracking. |
| `agent/nodes/` | Individual LangGraph nodes | Graph mutation, Cypher execution, scenario planning, safety checks. |
| `agent/mcp_integration.py` | Model Context Protocol bridge | Wraps `mcp-neo4j-cypher`, provides `Neo4jMCPClient` context helpers. |
| `agent/backend/app/` | FastAPI application | REST `/tools/*` endpoints, `/ws` WebSocket, event broker, settings management. |
| `agent/simulation_engine.py` | Simulation orchestration | Async job management with streaming status + mock adapter fallback. |
| `frontend/` | Vite-powered React workbench | Chat UI, Sigma.js canvas, Cypher console, simulation drawer, resilient streaming client. |
| `blueprint.txt` | Historical blueprint | Reference roadmap describing long-term milestones and connector strategy. |

## Data flow overview

1. **Graph ingestion** – The workbench uploads JSON via `POST /tools/load_graph`; the backend validates payloads and hands them to `MCPGraphOperations.load_graph`, which pipes them into Neo4j through Model Context Protocol.【F:agent/backend/app/api.py†L49-L98】
2. **Conversational loop** – Chat messages from the UI hit `/ws`, are acknowledged by the FastAPI broker, and are handed to the LangGraph runtime. The agent selects nodes (graph tools, scenario planner, summariser) and streams responses/events back to the client.【F:agent/backend/app/websocket.py†L16-L115】
3. **Cypher execution** – Queries are validated (`validate_cypher_query`) then executed via MCP. Summaries/records are normalised for the UI to render tabular results.【F:agent/backend/app/api.py†L100-L139】
4. **Simulation lifecycle** – Scenario launches call `SimulationEngine.start_simulation`, emitting incremental events. The mock adapter keeps UX flows functional while external BAS connectors are wired in.【F:agent/backend/app/api.py†L141-L206】【F:agent/simulation_engine.py†L1-L199】

## Getting started

### Prerequisites

| Tooling | Version | Notes |
| --- | --- | --- |
| Python | 3.10+ | Required for LangGraph agent + FastAPI backend. |
| Node.js | 20+ | Powers the Vite workbench and UI build tooling. |
| Neo4j / Memgraph | Optional | Enables live graph persistence; mock in-memory flow works without it. |
| `uv` (optional) | Latest | Simplifies spawning `mcp-neo4j-cypher` alongside the backend. |

### Backend

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .[dev]

# Launch REST + WebSocket services with auto-reload
uvicorn agent.backend.app.main:app --reload
```

The backend exposes REST endpoints at `http://localhost:8000/api` & `/tools`, and upgrades WebSocket sessions on `ws://localhost:8000/ws` for streaming agent traffic.【F:agent/backend/app/main.py†L1-L13】【F:agent/backend/app/api.py†L30-L139】

### Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

The dev server serves the workbench on `http://localhost:5173` by default. Configure `VITE_MCP_BASE_URL`/`VITE_WS_URL` (or their legacy `NEXT_PUBLIC_*` aliases) to point at the FastAPI service before launching.【F:frontend/lib/api.ts†L3-L47】

### Optional: Neo4j via MCP

1. Ensure Neo4j is reachable and set the `GRAPH_NEO4J_*` variables.
2. Install [`uv`](https://github.com/astral-sh/uv) so the backend can spawn `mcp-neo4j-cypher` using stdio transport.
3. Start the backend; MCP clients are initialised lazily when the first tool call arrives.【F:agent/backend/app/api.py†L49-L107】

If Neo4j or MCP tooling is absent, the backend gracefully falls back to mock implementations so demos still run.【F:agent/backend/app/api.py†L49-L206】

## Configuration reference

| Variable | Scope | Purpose | Default |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | Backend | Enables real LLM responses; mock text is used without it. | — |
| `OPENAI_MODEL` | Backend | Chat completion model for LangGraph. | `gpt-4o` |
| `GRAPH_NEO4J_URI` | Backend | Bolt URI for Neo4j/Memgraph. | `bolt://localhost:7687` |
| `GRAPH_NEO4J_USER` / `GRAPH_NEO4J_PASSWORD` | Backend | Credentials for the graph store. | `neo4j` / `neo4jtest` |
| `GRAPH_NEO4J_DATABASE` | Backend | Database name when using multi-db setups. | `neo4j` |
| `GRAPH_DEFAULT_CYPHER_LIMIT` | Backend | Automatic `LIMIT` appended to queries. | `100` |
| `GRAPH_ALLOW_WRITE_CYPHER` | Backend | Enables write-mode Cypher over the API. | `false` |
| `VITE_MCP_BASE_URL` | Frontend | REST base URL (legacy alias: `NEXT_PUBLIC_MCP_BASE_URL`). | `http://localhost:8000` |
| `VITE_WS_URL` | Frontend | WebSocket endpoint (legacy alias: `NEXT_PUBLIC_WS_URL`). | `ws://localhost:8000/ws` |

## Operating the workbench

1. **Load a graph** – Drag a JSON payload onto the uploader (`frontend/components/GraphUploader.tsx`). The API validates structure via `validate_graph_payload` and persists it through MCP.【F:agent/backend/app/api.py†L49-L98】
2. **Inspect & filter** – The Sigma.js canvas renders streamed nodes/edges, while the inspector panels respond to selection events (`frontend/components/DynamicInteractiveGraphCanvas.tsx`).
3. **Run Cypher queries** – Use the console to run read/write operations; responses appear inline with summary metadata for debugging.【F:agent/backend/app/api.py†L100-L139】
4. **Talk to the agent** – Chat messages travel over `/ws`; the LangGraph workflow a-invokes nodes and emits `agent.response` alongside structured logs.【F:agent/backend/app/websocket.py†L16-L115】
5. **Launch simulations** – Scenario controls call `/tools/start_attack`; the simulation engine or mock adapter issues progress ticks and final findings through the event broker.【F:agent/backend/app/api.py†L141-L206】【F:agent/simulation_engine.py†L1-L199】

## Developer workflow

| Layer | Checks | Command |
| --- | --- | --- |
| Python agent/backend | Tests | `pytest` |
| Python agent/backend | Linting | `ruff check agent/` |
| Frontend | Linting | `npm run lint` |
| Frontend | Type safety | `npm run typecheck` (add via `tsc --noEmit` if not already in scripts) |

Additional tips:

* WebSocket traces are logged via the FastAPI broker; run with `LOG_LEVEL=debug` to inspect traffic.【F:agent/backend/app/websocket.py†L16-L115】
* `SimulationEngine` can be extended with real BAS connectors by implementing the abstract adapter interface exposed in `agent/simulation_engine.py`.
* Tooling defaults to mock behaviours when dependencies are missing, making local onboarding painless.【F:agent/backend/app/api.py†L49-L206】

## Repository layout

```text
├── agent/
│   ├── backend/app/          # FastAPI service (REST, WebSocket, broker, settings)
│   ├── nodes/                # LangGraph nodes for graph + scenario operations
│   ├── prompts/              # Agent system instructions
│   ├── simulation_engine.py  # Async simulation job orchestration + adapters
│   ├── flow.py               # LangGraph graph definition
│   └── tests/                # Pytest suite
├── frontend/                 # React/Vite workbench (components, hooks, lib, styles)
├── blueprint.txt             # Original multi-track blueprint & roadmap
├── pyproject.toml            # Python packaging + dependencies
└── README.md                 # Project documentation (this file)
```

## Roadmap & current focus

* Harden MCP error handling and retry semantics when the Neo4j bridge is unavailable.【F:agent/backend/app/api.py†L49-L107】
* Expand scenario templates and integrate the first real BAS connector beyond the mock adapter.【F:agent/backend/app/api.py†L141-L206】【F:agent/simulation_engine.py†L1-L199】
* Improve front-end observability (metrics surfaced via `usePerformanceMonitor`) and add scenario reporting exports.【F:frontend/pages/index.tsx†L1-L119】
