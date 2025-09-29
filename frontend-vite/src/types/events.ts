export type AgentEventKind =
  | "agent.log"
  | "agent.step"
  | "agent.message"
  | "scenario.status"
  | "scenario.result"
  | "graph.replace"
  | "graph.highlight"
  | "notification";

export interface AgentEvent<TPayload = unknown> {
  id: string;
  type: AgentEventKind;
  createdAt: string;
  payload: TPayload;
  level?: "debug" | "info" | "warn" | "error";
  source?: string;
}

export type ConnectionState =
  | "idle"
  | "connecting"
  | "open"
  | "retrying"
  | "closed"
  | "error";

export interface ConnectionMetrics {
  attempts: number;
  lastConnectedAt?: string;
  lastDisconnectedAt?: string;
}

export type OutgoingAgentMessage =
  | {
      type: "agent.command";
      command: "chat";
      payload: { text: string };
    }
  | {
      type: "scenario.run";
      scenarioId: string;
      targetSelector: string;
      platform?: string;
      params?: Record<string, unknown>;
    }
  | {
      type: "graph.request";
      request: "full" | "delta";
      since?: string;
    };

export interface AgentMessagePayload {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface AgentStepPayload {
  name: string;
  request: Record<string, unknown>;
  response: Record<string, unknown>;
  elapsedMs?: number | null;
  error?: string | null;
}

export interface GraphHighlightPayload {
  nodeIds: string[];
}

export interface ScenarioStatusPayload {
  jobId: string;
  status: string;
  [key: string]: unknown;
}

export interface ScenarioResultPayload {
  jobId: string;
  findings: Record<string, unknown>;
}
