from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from agent.models import Edge, GraphMutation, GraphPayload, Node, ScenarioJob

from .graph_service import GraphService
from .settings import Settings, get_settings

router = APIRouter(prefix="/tools", tags=["tools"])


class UpdateRequest(BaseModel):
    attrs: Dict[str, Any] = Field(default_factory=dict)


class CypherRequest(BaseModel):
    query: str
    params: Optional[Dict[str, Any]] = None
    mode: str = Field(default="read", pattern="^(read|write)$")


class SubgraphRequest(BaseModel):
    node_ids: Optional[List[str]] = None
    limit: Optional[int] = Field(default=None, ge=1)


class AnnotateRequest(BaseModel):
    node_ids: List[str]
    tag: str


class StartAttackRequest(BaseModel):
    platform: str
    scenario_id: str
    target_selector: Dict[str, Any]
    parameters: Optional[Dict[str, Any]] = None


class MutationRequest(BaseModel):
    mutation: GraphMutation


@lru_cache(maxsize=1)
def get_service(settings: Optional[Settings] = None) -> GraphService:
    return GraphService(settings=settings)


def graph_service_dep() -> GraphService:
    settings = get_settings()
    return get_service(settings)


@router.post("/load_graph")
def load_graph(payload: GraphPayload, service: GraphService = Depends(graph_service_dep)):
    return service.load_graph(payload)


@router.post("/add_node")
def add_node(node: Node, service: GraphService = Depends(graph_service_dep)):
    return service.add_node(node)


@router.post("/update_node/{node_id}")
def update_node(node_id: str, request: UpdateRequest, service: GraphService = Depends(graph_service_dep)):
    return service.update_node(node_id, request.attrs)


@router.post("/delete_node/{node_id}")
def delete_node(node_id: str, service: GraphService = Depends(graph_service_dep)):
    return service.delete_node(node_id)


@router.post("/add_edge")
def add_edge(edge: Edge, service: GraphService = Depends(graph_service_dep)):
    return service.add_edge(edge)


@router.post("/update_edge/{edge_id}")
def update_edge(edge_id: str, request: UpdateRequest, service: GraphService = Depends(graph_service_dep)):
    return service.update_edge(edge_id, request.attrs)


@router.post("/delete_edge/{edge_id}")
def delete_edge(edge_id: str, service: GraphService = Depends(graph_service_dep)):
    return service.delete_edge(edge_id)


@router.post("/get_subgraph")
def get_subgraph(request: SubgraphRequest, service: GraphService = Depends(graph_service_dep)):
    return service.get_subgraph(node_ids=request.node_ids, limit=request.limit)


@router.post("/run_cypher")
def run_cypher(request: CypherRequest, service: GraphService = Depends(graph_service_dep)):
    return service.run_cypher(request.query, request.params, request.mode)


@router.post("/annotate_nodes")
def annotate_nodes(request: AnnotateRequest, service: GraphService = Depends(graph_service_dep)):
    return service.annotate_nodes(request.node_ids, request.tag)


@router.post("/apply_mutation")
def apply_mutation(request: MutationRequest, service: GraphService = Depends(graph_service_dep)):
    return service.apply_mutation(request.mutation)


@router.post("/start_attack")
def start_attack(request: StartAttackRequest, service: GraphService = Depends(graph_service_dep)):
    return service.start_attack(
        platform=request.platform,
        scenario_id=request.scenario_id,
        target_selector=request.target_selector,
        parameters=request.parameters,
    )


@router.get("/check_attack/{job_id}")
def check_attack(job_id: str, service: GraphService = Depends(graph_service_dep)):
    return service.check_attack(job_id)


@router.get("/fetch_results/{job_id}")
def fetch_results(job_id: str, service: GraphService = Depends(graph_service_dep)):
    return service.fetch_results(job_id)


@router.get("/health")
def health(settings: Settings = Depends(get_settings)):
    payload = {"neo4j_uri": settings.neo4j_uri is not None}
    return {"status": "ok", "details": payload}


def build_app() -> FastAPI:
    app = FastAPI(title="Graph MCP API")
    app.include_router(router)
    return app
