export interface GraphNode {
  id: string;
  labels: string[];
  attrs: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  attrs: Record<string, unknown>;
}

export interface GraphMetadata {
  source?: string;
  ingested_at?: string;
  [key: string]: unknown;
}

export interface GraphPayload {
  version: string;
  metadata: GraphMetadata;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface CypherResult {
  records: Array<Record<string, unknown>>;
  summary?: Record<string, unknown>;
}

export interface ScenarioRunRequest {
  platform: string;
  scenarioId: string;
  targetSelector: string;
  params?: Record<string, unknown>;
}

export interface ScenarioRunStatus {
  jobId: string;
  status: "pending" | "running" | "succeeded" | "failed";
  startedAt?: string;
  completedAt?: string;
  details?: string;
}
