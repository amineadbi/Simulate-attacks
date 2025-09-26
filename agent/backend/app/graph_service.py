from __future__ import annotations

import re
import uuid
from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException

from agent.models import (
    Edge,
    GraphMutation,
    GraphPayload,
    MutationType,
    Node,
    ScenarioJob,
    ScenarioPlan,
    ScenarioStatus,
)

from .db import get_driver_factory
from .settings import Settings, get_settings

_LABEL = re.compile(r"[^A-Za-z0-9_]")
_REL = re.compile(r"[^A-Za-z0-9_]")


class GraphService:
    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings or get_settings()
        self._driver_factory = get_driver_factory()
        self._nodes: Dict[str, Node] = {}
        self._edges: Dict[str, Edge] = {}
        self._jobs: Dict[str, ScenarioJob] = {}

    def load_graph(self, payload: GraphPayload) -> Dict[str, Any]:
        for node in payload.nodes:
            self._nodes[node.id] = node
        for edge in payload.edges:
            self._edges[edge.id] = edge
        driver = self._driver_factory.get_driver()
        if driver:
            with driver.session(database=self._settings.neo4j_database) as session:
                session.execute_write(lambda tx: self._write_nodes(tx, payload.nodes))
                session.execute_write(lambda tx: self._write_edges(tx, payload.edges))
        return {"nodes": len(payload.nodes), "edges": len(payload.edges)}

    def add_node(self, node: Node) -> Node:
        self._nodes[node.id] = node
        driver = self._driver_factory.get_driver()
        if driver:
            with driver.session(database=self._settings.neo4j_database) as session:
                session.execute_write(lambda tx: self._write_nodes(tx, [node]))
        return node

    def update_node(self, node_id: str, attrs: Dict[str, Any]) -> Node:
        existing = self._nodes.get(node_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Node not found")
        updated = existing.model_copy(update={"attrs": {**existing.attrs, **attrs}})
        self._nodes[node_id] = updated
        driver = self._driver_factory.get_driver()
        if driver:
            with driver.session(database=self._settings.neo4j_database) as session:
                session.execute_write(lambda tx: self._update_node_attrs(tx, node_id, attrs))
        return updated

    def delete_node(self, node_id: str) -> Dict[str, Any]:
        self._nodes.pop(node_id, None)
        removed_edges = [edge_id for edge_id, edge in list(self._edges.items()) if edge.source == node_id or edge.target == node_id]
        for edge_id in removed_edges:
            self._edges.pop(edge_id, None)
        driver = self._driver_factory.get_driver()
        if driver:
            with driver.session(database=self._settings.neo4j_database) as session:
                session.execute_write(lambda tx: self._delete_node(tx, node_id))
        return {"deleted": {"node": node_id, "edges": removed_edges}}

    def add_edge(self, edge: Edge) -> Edge:
        if edge.source not in self._nodes or edge.target not in self._nodes:
            raise HTTPException(status_code=400, detail="Source or target missing")
        self._edges[edge.id] = edge
        driver = self._driver_factory.get_driver()
        if driver:
            with driver.session(database=self._settings.neo4j_database) as session:
                session.execute_write(lambda tx: self._write_edges(tx, [edge]))
        return edge

    def update_edge(self, edge_id: str, attrs: Dict[str, Any]) -> Edge:
        existing = self._edges.get(edge_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Edge not found")
        updated = existing.model_copy(update={"attrs": {**existing.attrs, **attrs}})
        self._edges[edge_id] = updated
        driver = self._driver_factory.get_driver()
        if driver:
            with driver.session(database=self._settings.neo4j_database) as session:
                session.execute_write(lambda tx: self._update_edge_attrs(tx, edge_id, attrs))
        return updated

    def delete_edge(self, edge_id: str) -> Dict[str, Any]:
        self._edges.pop(edge_id, None)
        driver = self._driver_factory.get_driver()
        if driver:
            with driver.session(database=self._settings.neo4j_database) as session:
                session.execute_write(lambda tx: self._delete_edge(tx, edge_id))
        return {"deleted": edge_id}

    def get_subgraph(self, node_ids: Optional[List[str]] = None, limit: Optional[int] = None) -> GraphPayload:
        if node_ids:
            nodes = [node for node in self._nodes.values() if node.id in node_ids]
        else:
            nodes = list(self._nodes.values())
        if limit:
            nodes = nodes[:limit]
        node_set = {node.id for node in nodes}
        edges = [edge for edge in self._edges.values() if edge.source in node_set and edge.target in node_set]
        if limit:
            edges = edges[:limit]
        return GraphPayload(nodes=nodes, edges=edges)

    def run_cypher(self, query: str, params: Optional[Dict[str, Any]], mode: str) -> Dict[str, Any]:
        mode = (mode or 'read').lower()
        if mode not in {'read', 'write'}:
            raise HTTPException(status_code=400, detail="Invalid mode")
        driver = self._driver_factory.get_driver()
        if not driver:
            raise HTTPException(status_code=503, detail="Neo4j connection not configured")
        if mode == "write" and not self._settings.allow_write_cypher:
            raise HTTPException(status_code=403, detail="Write queries disabled")
        trimmed = query.strip()
        if "limit" not in trimmed.lower():
            trimmed = f"{trimmed}\nLIMIT {self._settings.default_cypher_limit}"
        with driver.session(database=self._settings.neo4j_database) as session:
            if mode == "write":
                records = session.execute_write(lambda tx: list(tx.run(trimmed, params or {})))
            else:
                records = session.execute_read(lambda tx: list(tx.run(trimmed, params or {})))
        data = [record.data() for record in records]
        return {"records": data, "count": len(data)}

    def annotate_nodes(self, node_ids: List[str], tag: str) -> Dict[str, Any]:
        for node_id in node_ids:
            node = self._nodes.get(node_id)
            if node:
                tags = set(node.attrs.get("tags", []))
                tags.add(tag)
                self._nodes[node_id] = node.model_copy(update={"attrs": {**node.attrs, "tags": sorted(tags)}})
        driver = self._driver_factory.get_driver()
        if driver:
            with driver.session(database=self._settings.neo4j_database) as session:
                session.execute_write(lambda tx: self._set_node_tag(tx, node_ids, tag))
        return {"annotated": node_ids, "tag": tag}

    def start_attack(
        self,
        platform: str,
        scenario_id: str,
        target_selector: Dict[str, Any],
        parameters: Optional[Dict[str, Any]] = None,
    ) -> ScenarioJob:
        params = parameters or {}
        plan = ScenarioPlan(
            scenario_id=scenario_id,
            platform=platform,
            objective=params.get("objective", ""),
            target_selector=target_selector,
            parameters=params,
        )
        job_id = str(uuid.uuid4())
        job = ScenarioJob(job_id=job_id, plan=plan, status=ScenarioStatus.PENDING, findings=None)
        self._jobs[job_id] = job
        return job

    def check_attack(self, job_id: str) -> ScenarioJob:
        job = self._jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    def complete_attack(self, job_id: str, status: ScenarioStatus, findings: Optional[Dict[str, Any]] = None) -> ScenarioJob:
        job = self.check_attack(job_id)
        updated = job.model_copy(update={"status": status, "findings": findings})
        self._jobs[job_id] = updated
        return updated

    def fetch_results(self, job_id: str) -> Dict[str, Any]:
        job = self.check_attack(job_id)
        if not job.findings:
            raise HTTPException(status_code=404, detail="Findings not available")
        return job.findings

    def apply_mutation(self, mutation: GraphMutation) -> Dict[str, Any]:
        if mutation.entity == "node":
            if mutation.mutation == MutationType.ADD:
                payload = {"id": mutation.target_id, **mutation.payload}
                node = Node.model_validate(payload)
                return self.add_node(node).model_dump(mode="json")
            if mutation.mutation == MutationType.UPDATE:
                return self.update_node(mutation.target_id, mutation.payload)
            if mutation.mutation == MutationType.DELETE:
                return self.delete_node(mutation.target_id)
        if mutation.entity == "edge":
            if mutation.mutation == MutationType.ADD:
                payload = {"id": mutation.target_id, **mutation.payload}
                edge = Edge.model_validate(payload)
                return self.add_edge(edge).model_dump(mode="json")
            if mutation.mutation == MutationType.UPDATE:
                return self.update_edge(mutation.target_id, mutation.payload)
            if mutation.mutation == MutationType.DELETE:
                return self.delete_edge(mutation.target_id)
        raise HTTPException(status_code=400, detail="Unsupported mutation")

    def _write_nodes(self, tx, nodes: Iterable[Node]) -> None:
        for node in nodes:
            labels = self._sanitize_labels(node.labels)
            label_clause = ":GraphNode" + "".join(f":{label}" for label in labels)
            tx.run(
                f"MERGE (n{label_clause} {{external_id: $id}}) SET n += $attrs, n.labels = $raw_labels",
                id=node.id,
                attrs=node.attrs,
                raw_labels=node.labels,
            )

    def _update_node_attrs(self, tx, node_id: str, attrs: Dict[str, Any]) -> None:
        tx.run(
            "MATCH (n:GraphNode {external_id: $id}) SET n += $attrs",
            id=node_id,
            attrs=attrs,
        )

    def _delete_node(self, tx, node_id: str) -> None:
        tx.run(
            "MATCH (n:GraphNode {external_id: $id}) DETACH DELETE n",
            id=node_id,
        )

    def _write_edges(self, tx, edges: Iterable[Edge]) -> None:
        for edge in edges:
            rel_type = self._sanitize_rel(edge.type)
            tx.run(
                (
                    "MATCH (source:GraphNode {external_id: $source}), (target:GraphNode {external_id: $target}) "
                    f"MERGE (source)-[r:{rel_type} {{external_id: $id}}]->(target) "
                    "SET r += $attrs, r.type = $raw_type"
                ),
                source=edge.source,
                target=edge.target,
                id=edge.id,
                attrs=edge.attrs,
                raw_type=edge.type,
            )

    def _update_edge_attrs(self, tx, edge_id: str, attrs: Dict[str, Any]) -> None:
        tx.run(
            "MATCH ()-[r {external_id: $id}]->() SET r += $attrs",
            id=edge_id,
            attrs=attrs,
        )

    def _delete_edge(self, tx, edge_id: str) -> None:
        tx.run(
            "MATCH ()-[r {external_id: $id}]->() DELETE r",
            id=edge_id,
        )

    def _set_node_tag(self, tx, node_ids: List[str], tag: str) -> None:
        tx.run(
            "MATCH (n:GraphNode) WHERE n.external_id IN $ids "
            "SET n.tags = CASE WHEN n.tags IS NULL THEN [$tag] WHEN $tag IN n.tags THEN n.tags ELSE n.tags + [$tag] END",
            ids=node_ids,
            tag=tag,
        )

    def _sanitize_labels(self, labels: Iterable[str]) -> List[str]:
        return [self._sanitize_label(label) for label in labels if label]

    def _sanitize_label(self, label: str) -> str:
        cleaned = _LABEL.sub("_", label).strip("_")
        return cleaned or "Node"

    def _sanitize_rel(self, rel: str) -> str:
        cleaned = _REL.sub("_", rel).upper().strip("_")
        return cleaned or "REL"


