export type AgentEventKind =
  | "agent.log"
  | "agent.step"
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

export interface ConnectionMetrics {
  attempts: number;
  lastConnectedAt?: string;
  lastDisconnectedAt?: string;
}

export type ConnectionState =
  | "idle"
  | "connecting"
  | "open"
  | "retrying"
  | "closed"
  | "error";

export type OutgoingAgentMessage =
  | {
      type: "agent.command";
      command: string;
      payload?: Record<string, unknown>;
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
