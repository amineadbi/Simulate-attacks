"use client";

import { useCallback, useMemo, useState } from "react";
import ConnectionIndicator from "../components/ConnectionIndicator";
import CypherQueryBar from "../components/CypherQueryBar";
import GraphCanvas from "../components/GraphCanvas";
import GraphUploader from "../components/GraphUploader";
import ScenarioControls from "../components/ScenarioControls";
import { useAgentEventStream } from "../lib/streaming";
import type { CypherResult, GraphPayload, ScenarioRunStatus } from "../types/graph";
import type { AgentEvent } from "../types/events";

interface LogEntry {
  id: string;
  message: string;
  createdAt: string;
  level?: "debug" | "info" | "warn" | "error";
}

const MAX_LOG_ENTRIES = 80;

function generateId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2, 11);
}

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
  const maybe = payload as Partial<ScenarioRunStatus>;
  if (typeof maybe.jobId === "string" && typeof maybe.status === "string") {
    return {
      jobId: maybe.jobId,
      status: maybe.status as ScenarioRunStatus["status"],
      startedAt: maybe.startedAt,
      completedAt: maybe.completedAt,
      details: maybe.details
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

export default function HomePage() {
  const [graphData, setGraphData] = useState<GraphPayload | null>(null);
  const [highlightedNodes, setHighlightedNodes] = useState<string[]>([]);
  const [scenarioStatus, setScenarioStatus] = useState<ScenarioRunStatus | null>(null);
  const [scenarioResults, setScenarioResults] = useState<unknown>(null);
  const [cypherResult, setCypherResult] = useState<CypherResult | null>(null);
  const [logEntries, setLogEntries] = useState<LogEntry[]>([]);

  const pushLog = useCallback(
    (entry: Omit<LogEntry, "id"> & { id?: string }) => {
      setLogEntries((prev) => [{ id: entry.id ?? generateId(), ...entry }, ...prev].slice(0, MAX_LOG_ENTRIES));
    },
    []
  );

  const handleGraphLoaded = useCallback(
    (payload: GraphPayload) => {
      setGraphData(payload);
      setHighlightedNodes([]);
      setScenarioResults(null);
      setScenarioStatus(null);
      pushLog({
        message: `Loaded graph with ${payload.nodes.length} nodes and ${payload.edges.length} edges`,
        createdAt: new Date().toISOString(),
        level: "info"
      });
    },
    [pushLog]
  );

  const handleCypher = useCallback(
    (result: CypherResult) => {
      setCypherResult(result);
      const ids = new Set<string>();
      result.records.forEach((record) => {
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
      setHighlightedNodes([...ids]);
      pushLog({
        message: `Cypher returned ${result.records.length} record(s)`,
        createdAt: new Date().toISOString(),
        level: "debug"
      });
    },
    [pushLog]
  );

  const handleStreamEvent = useCallback(
    (event: AgentEvent) => {
      const baseEntry: Omit<LogEntry, "id"> = {
        message: `${event.type}`,
        createdAt: event.createdAt,
        level: event.level ?? "info"
      };

      switch (event.type) {
        case "agent.log":
        case "agent.step": {
          const payload = event.payload as { message?: string; text?: string };
          pushLog({
            id: event.id,
            message: payload?.message ?? payload?.text ?? event.type,
            createdAt: event.createdAt,
            level: event.level ?? "info"
          });
          break;
        }
        case "scenario.status": {
          const status = coerceScenarioStatus(event.payload);
          if (status) {
            setScenarioStatus(status);
            pushLog({
              id: event.id,
              message: `Scenario ${status.jobId} is ${status.status}`,
              createdAt: event.createdAt,
              level: status.status === "failed" ? "error" : "info"
            });
          }
          break;
        }
        case "scenario.result": {
          setScenarioResults(event.payload);
          pushLog({
            id: event.id,
            message: "Scenario results received",
            createdAt: event.createdAt,
            level: "info"
          });
          break;
        }
        case "graph.replace": {
          if (isGraphPayload(event.payload)) {
            setGraphData(event.payload);
            pushLog({
              id: event.id,
              message: "Graph snapshot replaced from agent stream",
              createdAt: event.createdAt,
              level: "info"
            });
          }
          break;
        }
        case "graph.highlight": {
          const nodes = coerceHighlight(event.payload);
          if (nodes.length) {
            setHighlightedNodes(nodes);
            pushLog({
              id: event.id,
              message: `Highlighting ${nodes.length} node(s) from agent stream`,
              createdAt: event.createdAt,
              level: "debug"
            });
          }
          break;
        }
        case "notification": {
          const payload = event.payload as { message?: string };
          pushLog({
            id: event.id,
            message: payload?.message ?? "Notification received",
            createdAt: event.createdAt,
            level: event.level ?? "info"
          });
          break;
        }
        default: {
          pushLog({ ...baseEntry, id: event.id });
        }
      }
    },
    [pushLog]
  );

  const { status: connectionStatus, metrics, sendMessage } = useAgentEventStream({
    onEvent: handleStreamEvent
  });

  const scenarioSummary = useMemo(() => {
    if (!scenarioStatus) return "No scenario run yet";
    const { status, jobId } = scenarioStatus;
    return `Job ${jobId} is ${status}`;
  }, [scenarioStatus]);

  return (
    <div className="layout">
      <header className="header">
        <div className="headline">
          <h1>Graph Scenario Workbench</h1>
          <ConnectionIndicator state={connectionStatus} lastConnectedAt={metrics.lastConnectedAt} />
        </div>
        <p className="subtitle">Upload, inspect, and exercise your network graph in real time.</p>
      </header>
      <main className="main">
        <section className="left-pane">
          <GraphUploader onGraphLoaded={handleGraphLoaded} />
          <CypherQueryBar onResult={handleCypher} />
          <ScenarioControls
            connectionStatus={connectionStatus}
            latestStatus={scenarioStatus}
            sendMessage={sendMessage}
            onScenarioStarted={(status) => {
              setScenarioStatus(status);
              pushLog({
                message: `Scenario started (job ${status.jobId})`,
                createdAt: new Date().toISOString(),
                level: "info"
              });
            }}
            onScenarioError={(message) =>
              pushLog({
                message: `Scenario failed to start: ${message}`,
                createdAt: new Date().toISOString(),
                level: "error"
              })
            }
          />
          <section className="log-panel">
            <h2>Activity Log</h2>
            <ul>
              {logEntries.map((entry) => (
                <li key={entry.id} className={`log-entry level-${entry.level ?? "info"}`}>
                  <span className="timestamp">
                    {new Date(entry.createdAt).toLocaleTimeString()}
                  </span>
                  <span className="message">{entry.message}</span>
                </li>
              ))}
            </ul>
          </section>
          <section className="result-panel">
            <h2>Scenario Summary</h2>
            <p>{scenarioSummary}</p>
            {scenarioResults ? (
              <details>
                <summary>Inspect Raw Results</summary>
                <pre>{JSON.stringify(scenarioResults, null, 2)}</pre>
              </details>
            ) : null}
          </section>
          {cypherResult ? (
            <section className="result-panel">
              <h2>Cypher Result (latest)</h2>
              <pre>{JSON.stringify(cypherResult, null, 2)}</pre>
            </section>
          ) : null}
        </section>
        <section className="right-pane">
          <GraphCanvas graphData={graphData} highlightNodes={highlightedNodes} />
        </section>
      </main>
    </div>
  );
}
