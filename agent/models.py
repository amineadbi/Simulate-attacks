from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Node(BaseModel):
    id: str
    labels: List[str] = Field(default_factory=list)
    attrs: Dict[str, Any] = Field(default_factory=dict)


class Edge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    attrs: Dict[str, Any] = Field(default_factory=dict)


class GraphMetadata(BaseModel):
    source: Optional[str] = None
    ingested_at: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class GraphPayload(BaseModel):
    version: str = "1.0"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    nodes: List[Node] = Field(default_factory=list)
    edges: List[Edge] = Field(default_factory=list)

    def node_ids(self) -> List[str]:
        return [node.id for node in self.nodes]

    def edge_ids(self) -> List[str]:
        return [edge.id for edge in self.edges]


class MutationType(str, Enum):
    ADD = "add"
    UPDATE = "update"
    DELETE = "delete"


class GraphMutation(BaseModel):
    entity: str
    target_id: str
    mutation: MutationType
    payload: Dict[str, Any] = Field(default_factory=dict)


class GraphActionPlan(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    reasoning: str
    mutation: GraphMutation
    requires_confirmation: bool = False


class ScenarioStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScenarioPlan(BaseModel):
    scenario_id: str
    platform: str
    objective: str
    target_selector: Dict[str, Any] = Field(default_factory=dict)
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ScenarioJob(BaseModel):
    job_id: str
    plan: ScenarioPlan
    status: ScenarioStatus
    findings: Optional[Dict[str, Any]] = None


class ToolCallResult(BaseModel):
    name: str
    request: Dict[str, Any]
    response: Dict[str, Any]
    elapsed_ms: Optional[float] = None
    error: Optional[str] = None
