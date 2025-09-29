import type { AgentEvent, AgentMessagePayload, AgentStepPayload, GraphHighlightPayload, ScenarioResultPayload, ScenarioStatusPayload } from "../types/events";
import type { AppAction, LogEntry } from "../types/app-state";
import type { GraphPayload, ScenarioRunStatus } from "../types/graph";

export type EventHandler = (event: AgentEvent<any>, dispatch: React.Dispatch<AppAction>) => void;

function isGraphPayload(payload: unknown): payload is GraphPayload {
  return (
    typeof payload === "object" &&
    payload !== null &&
    Array.isArray((payload as Record<string, unknown>).nodes) &&
    Array.isArray((payload as Record<string, unknown>).edges)
  );
}

function coerceScenarioStatus(payload: unknown): ScenarioRunStatus | null {
  if (!payload || typeof payload !== "object") return null;
  const maybe = payload as Partial<ScenarioStatusPayload>;
  if (typeof maybe?.jobId === "string" && typeof maybe?.status === "string") {
    return {
      jobId: maybe.jobId,
      status: maybe.status as ScenarioRunStatus["status"],
      startedAt: maybe.startedAt as string | undefined,
      completedAt: maybe.completedAt as string | undefined,
      details: maybe.details as string | undefined
    };
  }
  return null;
}

function coerceHighlight(payload: unknown): string[] {
  if (!payload || typeof payload !== "object") return [];
  const maybeIds = (payload as Record<string, unknown>).nodeIds;
  if (Array.isArray(maybeIds)) {
    return maybeIds.map(String);
  }
  return [];
}

function extractCypherNodeIds(result: any): string[] {
  const ids = new Set<string>();
  if (!result?.records) return [];

  result.records.forEach((record: any) => {
    Object.values(record).forEach((value) => {
      if (value && typeof value === "object") {
        if (Array.isArray(value)) {
          value.forEach((entry) => {
            if (entry && typeof entry === "object" && "id" in entry) {
              ids.add(String((entry as Record<string, unknown>).id));
            }
          });
        } else if ("id" in (value as Record<string, unknown>)) {
          ids.add(String((value as Record<string, unknown>).id));
        }
      }
    });
  });

  return Array.from(ids);
}

// Individual event handlers
const handleAgentMessage: EventHandler = (event, dispatch) => {
  const payload = event.payload as AgentMessagePayload | undefined;
  if (!payload || typeof payload.content !== "string") {
    return;
  }

  dispatch({
    type: "CHAT_MESSAGE_ADDED",
    payload: {
      id: event.id,
      role: payload.role,
      content: payload.content,
      createdAt: event.createdAt
    }
  });

  if (payload.role === "assistant") {
    dispatch({ type: "AGENT_WAITING_SET", payload: false });
  }
};

const handleAgentLog: EventHandler = (event, dispatch) => {
  const payload = event.payload as { message?: string; text?: string } | undefined;
  const level = event.level ?? "info";

  dispatch({
    type: "LOG_ENTRY_ADDED",
    payload: {
      id: event.id,
      message: payload?.message ?? payload?.text ?? event.type,
      createdAt: event.createdAt,
      level
    }
  });

  if (level === "error") {
    dispatch({ type: "AGENT_WAITING_SET", payload: false });
  }
};

const handleAgentStep: EventHandler = (event, dispatch) => {
  const payload = event.payload as AgentStepPayload | undefined;

  dispatch({
    type: "LOG_ENTRY_ADDED",
    payload: {
      id: event.id,
      message: payload?.name ? `Tool ${payload.name}` : "Tool invocation",
      createdAt: event.createdAt,
      level: event.level ?? "debug"
    }
  });
};

const handleScenarioStatus: EventHandler = (event, dispatch) => {
  const status = coerceScenarioStatus(event.payload as ScenarioStatusPayload);
  if (!status) return;

  dispatch({ type: "SCENARIO_STATUS_UPDATED", payload: status });

  dispatch({
    type: "LOG_ENTRY_ADDED",
    payload: {
      id: event.id,
      message: `Scenario ${status.jobId} is ${status.status}`,
      createdAt: event.createdAt,
      level: status.status === "failed" ? "error" : "info"
    }
  });
};

const handleScenarioResult: EventHandler = (event, dispatch) => {
  const payload = event.payload as ScenarioResultPayload | undefined;
  if (!payload) return;

  dispatch({ type: "SCENARIO_RESULTS_SET", payload: payload.findings });

  dispatch({
    type: "LOG_ENTRY_ADDED",
    payload: {
      id: event.id,
      message: `Scenario results ready for ${payload.jobId}`,
      createdAt: event.createdAt,
      level: "info"
    }
  });
};

const handleGraphReplace: EventHandler = (event, dispatch) => {
  if (!isGraphPayload(event.payload)) return;

  dispatch({ type: "GRAPH_REPLACED", payload: event.payload });

  dispatch({
    type: "LOG_ENTRY_ADDED",
    payload: {
      id: event.id,
      message: "Graph snapshot replaced from agent stream",
      createdAt: event.createdAt,
      level: "info"
    }
  });
};

const handleGraphHighlight: EventHandler = (event, dispatch) => {
  const payload = event.payload as GraphHighlightPayload | undefined;
  const nodes = payload?.nodeIds ?? coerceHighlight(event.payload);

  if (nodes.length === 0) return;

  dispatch({ type: "NODES_HIGHLIGHTED", payload: nodes });

  dispatch({
    type: "LOG_ENTRY_ADDED",
    payload: {
      id: event.id,
      message: `Highlighting ${nodes.length} node(s) from agent stream`,
      createdAt: event.createdAt,
      level: "debug"
    }
  });
};

const handleNotification: EventHandler = (event, dispatch) => {
  const payload = event.payload as { message?: string } | undefined;

  dispatch({
    type: "LOG_ENTRY_ADDED",
    payload: {
      id: event.id,
      message: payload?.message ?? "Notification received",
      createdAt: event.createdAt,
      level: event.level ?? "info"
    }
  });
};

const handleDefault: EventHandler = (event, dispatch) => {
  dispatch({
    type: "LOG_ENTRY_ADDED",
    payload: {
      id: event.id,
      message: `${event.type}`,
      createdAt: event.createdAt,
      level: event.level ?? "info"
    }
  });
};

// Event handler registry
export const eventHandlers: Record<string, EventHandler> = {
  "agent.message": handleAgentMessage,
  "agent.log": handleAgentLog,
  "agent.step": handleAgentStep,
  "scenario.status": handleScenarioStatus,
  "scenario.result": handleScenarioResult,
  "graph.replace": handleGraphReplace,
  "graph.highlight": handleGraphHighlight,
  "notification": handleNotification,
};

// Main event processor
export function processEvent(event: AgentEvent<any>, dispatch: React.Dispatch<AppAction>): void {
  const handler = eventHandlers[event.type] || handleDefault;
  handler(event, dispatch);
}

// Helper functions for complex operations
export function handleGraphLoaded(payload: GraphPayload, dispatch: React.Dispatch<AppAction>): void {
  dispatch({ type: "GRAPH_LOADED", payload });

  dispatch({
    type: "LOG_ENTRY_ADDED",
    payload: {
      message: `Loaded graph with ${payload.nodes.length} nodes and ${payload.edges.length} edges`,
      createdAt: new Date().toISOString(),
      level: "info"
    }
  });
}

export function handleCypherResult(result: any, dispatch: React.Dispatch<AppAction>): void {
  dispatch({ type: "CYPHER_RESULT_SET", payload: result });

  const ids = extractCypherNodeIds(result);
  if (ids.length > 0) {
    dispatch({ type: "NODES_HIGHLIGHTED", payload: ids });
  }

  dispatch({
    type: "LOG_ENTRY_ADDED",
    payload: {
      message: `Cypher returned ${result.records?.length || 0} record(s)`,
      createdAt: new Date().toISOString(),
      level: "debug"
    }
  });
}

export function handleConnectionStatusChange(status: string, dispatch: React.Dispatch<AppAction>): void {
  const message =
    status === "open" ? "Agent stream connected" :
    status === "retrying" ? "Agent stream retrying" :
    status === "error" ? "Agent stream encountered an error" :
    status === "closed" ? "Agent stream closed" :
    `Agent stream status: ${status}`;

  const level = status === "error" ? "error" : status === "retrying" ? "warn" : "info";

  dispatch({
    type: "LOG_ENTRY_ADDED",
    payload: {
      message,
      createdAt: new Date().toISOString(),
      level
    }
  });
}