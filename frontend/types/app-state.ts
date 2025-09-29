import type { AgentEvent, ConnectionState } from "./events";
import type { CypherResult, GraphPayload, ScenarioRunStatus } from "./graph";

export interface LogEntry {
  id: string;
  message: string;
  createdAt: string;
  level?: "debug" | "info" | "warn" | "error";
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  createdAt: string;
}

export interface AppState {
  // Graph data
  graphData: GraphPayload | null;
  highlightedNodes: string[];

  // Scenario management
  scenarioStatus: ScenarioRunStatus | null;
  scenarioResults: unknown;

  // Query results
  cypherResult: CypherResult | null;

  // UI state
  logEntries: LogEntry[];
  chatMessages: ChatMessage[];
  isWaitingForAgent: boolean;

  // Connection state
  connectionStatus: ConnectionState;
}

export type AppAction =
  | { type: "GRAPH_LOADED"; payload: GraphPayload }
  | { type: "GRAPH_REPLACED"; payload: GraphPayload }
  | { type: "NODES_HIGHLIGHTED"; payload: string[] }
  | { type: "SCENARIO_STATUS_UPDATED"; payload: ScenarioRunStatus }
  | { type: "SCENARIO_RESULTS_SET"; payload: unknown }
  | { type: "CYPHER_RESULT_SET"; payload: CypherResult }
  | { type: "LOG_ENTRY_ADDED"; payload: Omit<LogEntry, "id"> & { id?: string } }
  | { type: "CHAT_MESSAGE_ADDED"; payload: ChatMessage }
  | { type: "AGENT_WAITING_SET"; payload: boolean }
  | { type: "CONNECTION_STATUS_CHANGED"; payload: ConnectionState }
  | { type: "AGENT_EVENT_RECEIVED"; payload: AgentEvent };

export const MAX_LOG_ENTRIES = 80;
export const MAX_CHAT_MESSAGES = 120;

function generateId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2, 11);
}

export function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case "GRAPH_LOADED":
    case "GRAPH_REPLACED":
      return {
        ...state,
        graphData: action.payload,
        highlightedNodes: [],
        scenarioResults: null,
        scenarioStatus: null,
      };

    case "NODES_HIGHLIGHTED":
      return {
        ...state,
        highlightedNodes: action.payload,
      };

    case "SCENARIO_STATUS_UPDATED":
      return {
        ...state,
        scenarioStatus: action.payload,
      };

    case "SCENARIO_RESULTS_SET":
      return {
        ...state,
        scenarioResults: action.payload,
      };

    case "CYPHER_RESULT_SET":
      return {
        ...state,
        cypherResult: action.payload,
      };

    case "LOG_ENTRY_ADDED":
      const logEntry = {
        id: action.payload.id ?? generateId(),
        ...action.payload,
      };
      return {
        ...state,
        logEntries: [logEntry, ...state.logEntries].slice(0, MAX_LOG_ENTRIES),
      };

    case "CHAT_MESSAGE_ADDED":
      // Check for duplicates by ID
      if (state.chatMessages.some(msg => msg.id === action.payload.id)) {
        return state;
      }
      return {
        ...state,
        chatMessages: [...state.chatMessages, action.payload].slice(-MAX_CHAT_MESSAGES),
      };

    case "AGENT_WAITING_SET":
      return {
        ...state,
        isWaitingForAgent: action.payload,
      };

    case "CONNECTION_STATUS_CHANGED":
      return {
        ...state,
        connectionStatus: action.payload,
      };

    default:
      return state;
  }
}

export const initialAppState: AppState = {
  graphData: null,
  highlightedNodes: [],
  scenarioStatus: null,
  scenarioResults: null,
  cypherResult: null,
  logEntries: [],
  chatMessages: [],
  isWaitingForAgent: false,
  connectionStatus: "idle",
};