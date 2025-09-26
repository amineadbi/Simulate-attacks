import { useCallback, useEffect, useRef, useState } from "react";
import type {
  AgentEvent,
  ConnectionMetrics,
  ConnectionState,
  OutgoingAgentMessage
} from "../types/events";

const DEFAULT_WS_URL = "ws://localhost:8000/ws";
const BACKOFF_BASE_MS = 1000;
const BACKOFF_MAX_MS = 15000;

interface UseAgentEventStreamOptions {
  autoReconnect?: boolean;
  onEvent?: (event: AgentEvent) => void;
  onStatusChange?: (status: ConnectionState) => void;
}

interface AgentEventStream {
  status: ConnectionState;
  metrics: ConnectionMetrics;
  sendMessage: (message: OutgoingAgentMessage) => void;
  close: () => void;
  reconnect: () => void;
}

function computeBackoff(attempt: number): number {
  const cappedAttempt = Math.min(attempt, 8);
  const jitter = Math.random() * 0.4 + 0.8;
  return Math.min(BACKOFF_BASE_MS * 2 ** cappedAttempt * jitter, BACKOFF_MAX_MS);
}

export function useAgentEventStream({
  autoReconnect = true,
  onEvent,
  onStatusChange
}: UseAgentEventStreamOptions = {}): AgentEventStream {
  const wsUrl = useRef<string>(process.env.NEXT_PUBLIC_WS_URL ?? DEFAULT_WS_URL);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const attemptsRef = useRef<number>(0);
  const lastConnectedRef = useRef<string>();
  const lastDisconnectedRef = useRef<string>();
  const manualCloseRef = useRef<boolean>(false);
  const onEventRef = useRef<typeof onEvent>();
  const onStatusRef = useRef<typeof onStatusChange>();

  const [status, setStatus] = useState<ConnectionState>("idle");

  onEventRef.current = onEvent;
  onStatusRef.current = onStatusChange;

  const updateStatus = useCallback((next: ConnectionState) => {
    setStatus(next);
    onStatusRef.current?.(next);
  }, []);

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      window.clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  const cleanupSocket = useCallback(() => {
    const socket = socketRef.current;
    if (socket) {
      socket.onopen = null;
      socket.onmessage = null;
      socket.onerror = null;
      socket.onclose = null;
      socketRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    clearReconnectTimer();
    cleanupSocket();

    updateStatus("connecting");

    try {
      const socket = new WebSocket(wsUrl.current);
      socketRef.current = socket;

      socket.onopen = () => {
        attemptsRef.current = 0;
        lastConnectedRef.current = new Date().toISOString();
        updateStatus("open");
      };

      socket.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data) as AgentEvent;
          onEventRef.current?.(parsed);
        } catch (error) {
          console.error("Failed to parse WebSocket payload", error, event.data);
        }
      };

      socket.onerror = (event) => {
        console.error("WebSocket encountered an error", event);
        updateStatus("error");
      };

      socket.onclose = () => {
        lastDisconnectedRef.current = new Date().toISOString();
        cleanupSocket();
        if (manualCloseRef.current) {
          updateStatus("closed");
          return;
        }
        updateStatus("closed");
        if (autoReconnect) {
          const delay = computeBackoff(attemptsRef.current);
          reconnectTimeoutRef.current = window.setTimeout(() => {
            reconnectTimeoutRef.current = null;
            attemptsRef.current += 1;
            updateStatus("retrying");
            connect();
          }, delay) as unknown as number;
        }
      };
    } catch (error) {
      console.error("WebSocket connection failed", error);
      updateStatus("error");
      if (autoReconnect) {
        const delay = computeBackoff(attemptsRef.current);
        reconnectTimeoutRef.current = window.setTimeout(() => {
          reconnectTimeoutRef.current = null;
          attemptsRef.current += 1;
          updateStatus("retrying");
          connect();
        }, delay) as unknown as number;
      }
    }
  }, [autoReconnect, cleanupSocket, clearReconnectTimer, updateStatus]);

  const close = useCallback(() => {
    manualCloseRef.current = true;
    clearReconnectTimer();
    cleanupSocket();
    socketRef.current?.close();
    updateStatus("closed");
  }, [cleanupSocket, clearReconnectTimer, updateStatus]);

  const reconnect = useCallback(() => {
    manualCloseRef.current = false;
    attemptsRef.current = 0;
    connect();
  }, [connect]);

  const sendMessage = useCallback((message: OutgoingAgentMessage) => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      console.warn("Attempted to send over closed WebSocket", message);
      return;
    }
    socket.send(JSON.stringify(message));
  }, []);

  useEffect(() => {
    manualCloseRef.current = false;
    attemptsRef.current = 0;
    connect();
    return () => {
      manualCloseRef.current = true;
      clearReconnectTimer();
      const socket = socketRef.current;
      socketRef.current = null;
      socket?.close();
      cleanupSocket();
    };
  }, [clearReconnectTimer, cleanupSocket, connect]);

  return {
    status,
    metrics: {
      attempts: attemptsRef.current,
      lastConnectedAt: lastConnectedRef.current,
      lastDisconnectedAt: lastDisconnectedRef.current
    },
    sendMessage,
    close,
    reconnect
  };
}
