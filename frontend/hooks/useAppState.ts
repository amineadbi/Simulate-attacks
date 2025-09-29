import { useReducer, useCallback } from "react";
import { appReducer, initialAppState, type AppState, type AppAction } from "../types/app-state";
import { processEvent, handleGraphLoaded, handleCypherResult, handleConnectionStatusChange } from "../lib/event-handlers";
import { validateWebSocketMessage, validateGraphData, checkGraphLimits, AppError } from "../lib/error-recovery";
import type { AgentEvent, ConnectionState } from "../types/events";
import type { GraphPayload, CypherResult } from "../types/graph";

export function useAppState() {
  const [state, dispatch] = useReducer(appReducer, initialAppState);

  // Event handlers with validation and error recovery
  const handleStreamEvent = useCallback((event: AgentEvent<any>) => {
    try {
      // Validate message format
      if (!validateWebSocketMessage(event)) {
        console.warn("Invalid WebSocket message received:", event);
        return;
      }

      processEvent(event, dispatch);
    } catch (error) {
      console.error("Error processing WebSocket event:", error);
      dispatch({
        type: "LOG_ENTRY_ADDED",
        payload: {
          message: `Error processing event: ${(error as Error).message}`,
          createdAt: new Date().toISOString(),
          level: "error",
        },
      });
    }
  }, []);

  const handleGraphLoadedEvent = useCallback((payload: GraphPayload) => {
    try {
      // Validate graph data
      const validation = checkGraphLimits(payload);

      if (!validation.valid) {
        dispatch({
          type: "LOG_ENTRY_ADDED",
          payload: {
            message: `Graph validation failed: ${validation.errors.join(", ")}`,
            createdAt: new Date().toISOString(),
            level: "error",
          },
        });
        return;
      }

      // Show warnings for large graphs
      validation.warnings.forEach(warning => {
        dispatch({
          type: "LOG_ENTRY_ADDED",
          payload: {
            message: warning,
            createdAt: new Date().toISOString(),
            level: "warn",
          },
        });
      });

      handleGraphLoaded(payload, dispatch);
    } catch (error) {
      console.error("Error loading graph:", error);
      dispatch({
        type: "LOG_ENTRY_ADDED",
        payload: {
          message: `Failed to load graph: ${(error as Error).message}`,
          createdAt: new Date().toISOString(),
          level: "error",
        },
      });
    }
  }, []);

  const handleCypherResultEvent = useCallback((result: CypherResult) => {
    handleCypherResult(result, dispatch);
  }, []);

  const handleStatusChange = useCallback((status: ConnectionState) => {
    dispatch({ type: "CONNECTION_STATUS_CHANGED", payload: status });
    handleConnectionStatusChange(status, dispatch);
  }, []);

  const setWaitingForAgent = useCallback((waiting: boolean) => {
    dispatch({ type: "AGENT_WAITING_SET", payload: waiting });
  }, []);

  return {
    state,
    dispatch,
    handlers: {
      handleStreamEvent,
      handleGraphLoadedEvent,
      handleCypherResultEvent,
      handleStatusChange,
      setWaitingForAgent,
    },
  };
}