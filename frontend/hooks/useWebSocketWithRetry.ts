import { useCallback, useRef } from "react";
import { useAgentEventStream } from "../lib/streaming";
import type { AgentEvent, ConnectionState, OutgoingAgentMessage } from "../types/events";

interface UseWebSocketWithRetryOptions {
  onEvent?: (event: AgentEvent<any>) => void;
  onStatusChange?: (status: ConnectionState) => void;
  maxRetries?: number;
  retryDelay?: number;
}

export function useWebSocketWithRetry({
  onEvent,
  onStatusChange,
  maxRetries = 5,
  retryDelay = 1000,
}: UseWebSocketWithRetryOptions) {
  const retryCountRef = useRef(0);
  const lastEventRef = useRef<AgentEvent<any> | null>(null);
  const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isManualCloseRef = useRef(false);

  const handleEvent = useCallback((event: AgentEvent<any>) => {
    lastEventRef.current = event;
    onEvent?.(event);
  }, [onEvent]);

  // Create a ref to store the reconnect function
  const reconnectRef = useRef<(() => void) | null>(null);

  const handleStatusChange = useCallback((status: ConnectionState) => {
    // Clear any pending retry when successfully connected
    if (status === "open") {
      retryCountRef.current = 0;
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
        retryTimeoutRef.current = null;
      }
    }

    // Auto-retry on disconnect unless it was manual
    if (status === "closed" && !isManualCloseRef.current && retryCountRef.current < maxRetries) {
      const delay = Math.min(retryDelay * Math.pow(2, retryCountRef.current), 10000); // Exponential backoff, max 10s
      console.log(`WebSocket disconnected. Retrying in ${delay}ms (attempt ${retryCountRef.current + 1}/${maxRetries})`);

      retryTimeoutRef.current = setTimeout(() => {
        retryCountRef.current++;
        if (reconnectRef.current) {
          reconnectRef.current();
        }
      }, delay);
    } else if (status === "closed" && retryCountRef.current >= maxRetries) {
      console.error("Max retry attempts reached. Please check your connection.");
    }

    onStatusChange?.(status);
  }, [onStatusChange, maxRetries, retryDelay]);

  const { status, metrics, sendMessage, close, reconnect } = useAgentEventStream({
    onEvent: handleEvent,
    onStatusChange: handleStatusChange,
  });

  // Store the reconnect function in the ref
  reconnectRef.current = reconnect;

  const sendMessageSafely = useCallback((message: OutgoingAgentMessage) => {
    if (status === "open") {
      try {
        sendMessage(message);
      } catch (error) {
        console.error("Error sending WebSocket message:", error);
        // Try to reconnect on send error
        if (retryCountRef.current < maxRetries && reconnectRef.current) {
          console.log("Attempting to reconnect after send error...");
          retryCountRef.current++;
          reconnectRef.current();
        }
      }
    } else {
      console.warn("Cannot send message: WebSocket not connected", { status, message });
      // Queue message for retry when reconnected could be added here
    }
  }, [status, sendMessage, maxRetries]);

  const forceReconnect = useCallback(() => {
    isManualCloseRef.current = false; // Reset manual close flag
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }

    if (retryCountRef.current < maxRetries && reconnectRef.current) {
      retryCountRef.current++;
      reconnectRef.current();
    } else {
      console.error("Max retry attempts reached");
    }
  }, [maxRetries]);

  const closeConnection = useCallback(() => {
    isManualCloseRef.current = true; // Mark as manual close
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }
    close();
  }, [close]);

  // Cleanup on unmount
  const cleanup = useCallback(() => {
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }
  }, []);

  return {
    status,
    metrics,
    sendMessage: sendMessageSafely,
    close: closeConnection,
    reconnect: forceReconnect,
    retryCount: retryCountRef.current,
    lastEvent: lastEventRef.current,
    cleanup,
  };
}