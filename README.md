# Network Defense Graph Agent

A **LangGraph-based conversational agent** for network defense analysis using **Neo4j graph database** and **Model Context Protocol (MCP)** for tool integration.

## 🏗️ Architecture

```
Frontend (Next.js + Sigma.js)
    ↓ WebSocket
Backend (FastAPI + WebSocket)
    ↓ Orchestration
LangGraph Agent
    ↓ MCP Protocol (stdio)
Neo4j MCP Server (mcp-neo4j-cypher)
    ↓ Optimized Neo4j Driver
Neo4j Database
```

### Key Components

- **🤖 LangGraph Agent**: Conversational orchestrator with intent classification, graph operations, and scenario planning
- **📊 Neo4j Graph Database**: Network topology storage and analysis
- **🔌 MCP Integration**: Standard protocol using `langchain-mcp-adapters` with stdio transport
- **🎨 React Frontend**: Graph visualization with Sigma.js and real-time WebSocket updates
- **⚡ FastAPI Backend**: Minimal API layer with WebSocket support

## 🚀 Quick Start

### Prerequisites
- **Docker & Docker Compose**
- **Python ≥3.10** (for local development)
- **Node.js 20+** (for frontend development)

### 1. Start the Full Stack
```bash
# Clone and navigate to project
git clone <repo-url>
cd LOL

# Start all services
docker compose up --build
```

### 2. Access Services
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **Neo4j Browser**: http://localhost:7474 (neo4j/neo4jtest)

### 3. Environment Variables
Create `.env` file in project root:
```bash
# Required
OPENAI_API_KEY=your_openai_api_key

# Optional (with defaults)
OPENAI_MODEL=gpt-4o
AGENT_TEMPERATURE=0.1
DEBUG=false
```

## 💻 Development

### Backend Development
```bash
# Install dependencies in virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -e .

# Run tests
pytest

# Lint code
ruff check agent/
```

### Frontend Development
```bash
cd frontend

# Install dependencies
npm install

# Development server
npm run dev

# Build production
npm run build

# Lint
npm run lint
```

## 🔧 Key Technologies

### Backend Stack
- **LangGraph**: Agent workflow orchestration
- **LangChain**: LLM abstraction and tools
- **FastAPI**: Async web framework
- **Pydantic**: Data validation and serialization
- **langchain-mcp-adapters**: MCP protocol integration
- **mcp-neo4j-cypher**: Neo4j MCP server

### Frontend Stack
- **Next.js 14**: React framework with TypeScript
- **Sigma.js**: Graph visualization
- **Graphology**: Graph data structures
- **WebSocket**: Real-time communication

### Database
- **Neo4j 5.21**: Graph database with APOC procedures

## 📁 Project Structure

```
├── agent/                          # LangGraph agent core
│   ├── flow.py                     # Main LangGraph workflow
│   ├── config.py                   # Configuration management
│   ├── models.py                   # Pydantic data models
│   ├── state.py                    # LangGraph state definition
│   ├── tools.py                    # Tool registry (legacy)
│   ├── mcp_integration.py          # MCP client for Neo4j
│   ├── cypher_operations.py        # Cypher query builders
│   ├── nodes/                      # LangGraph nodes
│   │   ├── intent_classifier.py    # Route conversations
│   │   ├── graph_tools.py          # Graph operations via MCP
│   │   ├── scenario_planner.py     # Attack simulation
│   │   └── cypher.py               # Cypher query execution
│   ├── prompts/
│   │   └── system.md               # Agent system prompt
│   └── backend/                    # FastAPI application
│       └── app/
│           ├── main.py             # FastAPI app entry
│           ├── api.py              # API routes
│           ├── websocket.py        # WebSocket handlers
│           └── settings.py         # App configuration
├── frontend/                       # Next.js React app
│   ├── components/                 # React components
│   │   ├── GraphCanvas.tsx         # Basic graph visualization
│   │   ├── InteractiveGraphCanvas.tsx  # Advanced graph features
│   │   ├── GraphUploader.tsx       # Graph data upload
│   │   └── ConnectionIndicator.tsx # WebSocket status
│   ├── hooks/                      # React hooks
│   │   ├── useWebSocketWithRetry.ts # WebSocket management
│   │   └── useAppState.ts          # Application state
│   ├── lib/                        # Utilities
│   │   ├── api.ts                  # API client
│   │   ├── streaming.ts            # WebSocket streaming
│   │   └── event-handlers.ts       # Event processing
│   ├── types/                      # TypeScript types
│   └── public/
│       └── sample-graph.json       # Sample network topology
├── docker-compose.yml              # Container orchestration
├── pyproject.toml                  # Python dependencies
└── CLAUDE.md                       # AI assistant guidance
```

## 🔌 MCP Integration

The agent uses **Model Context Protocol (MCP)** for tool integration:

### Neo4j MCP Server
- **Package**: `mcp-neo4j-cypher@0.3.0`
- **Transport**: stdio (via `uvx`)
- **Tools**: `run-cypher`, `get-schema`
- **Connection**: Environment variables in docker-compose.yml

### Graph Operations
All graph operations are now handled via MCP:
```python
# Example: Add node via MCP
async with Neo4jMCPClient() as client:
    result = await client.run_cypher(
        "CREATE (n:Host {id: $id}) SET n += $props RETURN n",
        {"id": "server-1", "props": {"ip": "10.1.1.100"}}
    )
```

## 📊 Graph Data Format

### Nodes
```json
{
  "id": "server-1",
  "labels": ["Host", "Linux", "Critical"],
  "attrs": {
    "name": "Web Server",
    "ip": "10.1.1.100",
    "role": "webserver"
  }
}
```

### Edges
```json
{
  "id": "e1",
  "source": "workstation-1",
  "target": "server-1",
  "type": "allowed_tcp",
  "attrs": {
    "port": 443,
    "proto": "tcp"
  }
}
```

## 🧪 Testing

### Load Sample Data
1. Visit http://localhost:3000
2. Click "Load Sample Graph"
3. Verify graph visualization renders correctly
4. Check Neo4j Browser for data: `MATCH (n) RETURN n LIMIT 25`

### WebSocket Communication
- Open browser developer tools
- Watch Network tab for WebSocket connection
- Test agent interaction via chat interface

## 🔍 Troubleshooting

### Common Issues

**Neo4j Connection Errors**
- Verify Neo4j container is healthy: `docker compose ps`
- Check logs: `docker compose logs neo4j`
- Test connection: `docker exec lol-neo4j-1 cypher-shell -u neo4j -p neo4jtest "RETURN 1"`

**MCP Integration Issues**
- Verify `mcp-neo4j-cypher` can be installed: `uvx --help`
- Check environment variables in docker-compose.yml
- Review agent logs for MCP errors

**Frontend Build Errors**
- Ensure Node.js 20+ is installed
- Clear node_modules: `rm -rf frontend/node_modules && npm install`
- Check TypeScript errors: `cd frontend && npm run build`

### Development Logs
```bash
# Backend logs
docker compose logs backend -f

# Frontend logs
docker compose logs frontend -f

# Neo4j logs
docker compose logs neo4j -f
```

## 🚧 Current Status

✅ **Completed**
- MCP-based Neo4j integration
- Graph visualization with edge type mapping
- WebSocket communication
- Docker containerization
- Frontend/backend CORS configuration

🔄 **In Progress**
- Agent conversation flows
- Scenario planning integration
- Advanced graph analysis features

## 📄 License

This project is part of a network defense research initiative.