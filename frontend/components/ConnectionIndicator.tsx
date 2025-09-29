"use client";

import type { ConnectionState } from "../types/events";

interface ConnectionIndicatorProps {
  state: ConnectionState;
  lastConnectedAt?: string;
}

const LABELS: Record<ConnectionState, string> = {
  idle: "Idle",
  connecting: "Connecting",
  open: "Streaming",
  retrying: "Reconnecting",
  closed: "Offline",
  error: "Error"
};

export default function ConnectionIndicator({ state, lastConnectedAt }: ConnectionIndicatorProps) {
  return (
    <div className={`indicator indicator-${state}`}>
      <span className="dot" aria-hidden="true" />
      <span>{LABELS[state]}</span>
      {lastConnectedAt ? (
        <span className="meta" title={`Last connected ${lastConnectedAt}`}>
          - {new Date(lastConnectedAt).toLocaleTimeString()}
        </span>
      ) : null}
    </div>
  );
}
