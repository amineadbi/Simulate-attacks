"use client";

import { useCallback, useMemo, useState } from "react";
import CypherQueryBar from "../components/CypherQueryBar";
import GraphCanvas from "../components/GraphCanvas";
import GraphUploader from "../components/GraphUploader";
import ScenarioControls from "../components/ScenarioControls";
import type { CypherResult, GraphPayload, ScenarioRunStatus } from "../types/graph";

function extractNodeIds(result: CypherResult): string[] {
  const nodeIds = new Set<string>();
  result.records.forEach((record) => {
    Object.values(record).forEach((value) => {
      if (value && typeof value === "object") {
        if ("id" in (value as Record<string, unknown>)) {
          const id = String((value as Record<string, unknown>).id);
          nodeIds.add(id);
        }
        if (Array.isArray(value)) {
          value.forEach((entry) => {
            if (entry && typeof entry === "object" && "id" in entry) {
              const id = String((entry as Record<string, unknown>).id);
              nodeIds.add(id);
            }
          });
        }
      }
    });
  });
  return [...nodeIds];
}

export default function HomePage() {
  const [graphData, setGraphData] = useState<GraphPayload | null>(null);
  const [highlightedNodes, setHighlightedNodes] = useState<string[]>([]);
  const [scenarioStatus, setScenarioStatus] = useState<ScenarioRunStatus | null>(null);
  const [scenarioResults, setScenarioResults] = useState<unknown>(null);
  const [scenarioLog, setScenarioLog] = useState<string[]>([]);
  const [cypherResult, setCypherResult] = useState<CypherResult | null>(null);

  const handleGraphLoaded = useCallback((payload: GraphPayload) => {
    setGraphData(payload);
    setHighlightedNodes([]);
    setScenarioResults(null);
    setScenarioStatus(null);
    setScenarioLog((prev) => ["Loaded new graph", ...prev]);
  }, []);

  const handleCypher = useCallback((result: CypherResult) => {
    setCypherResult(result);
    const ids = extractNodeIds(result);
    setHighlightedNodes(ids);
    setScenarioLog((prev) => [
      `Cypher returned ${result.records.length} record(s)`,
      ...prev
    ]);
  }, []);

  const scenarioSummary = useMemo(() => {
    if (!scenarioStatus) return "No scenario run yet";
    const { status, jobId } = scenarioStatus;
    return `Job ${jobId} is ${status}`;
  }, [scenarioStatus]);

  return (
    <div className="layout">
      <header className="header">
        <h1>Graph Scenario Workbench</h1>
        <p className="subtitle">Upload, inspect, and exercise your network graph.</p>
      </header>
      <main className="main">
        <section className="left-pane">
          <GraphUploader onGraphLoaded={handleGraphLoaded} />
          <CypherQueryBar onResult={handleCypher} />
          <ScenarioControls
            onScenarioStarted={(status) => {
              setScenarioStatus(status);
              setScenarioLog((prev) => [`Scenario started (job ${status.jobId})`, ...prev]);
            }}
            onScenarioStatus={(status) => {
              setScenarioStatus(status);
              setScenarioLog((prev) => [`Scenario status: ${status.status}`, ...prev]);
            }}
            onScenarioResults={(results) => {
              setScenarioResults(results);
              setScenarioLog((prev) => ["Scenario results received", ...prev]);
            }}
          />
          <section className="log-panel">
            <h2>Activity Log</h2>
            <ul>
              {scenarioLog.slice(0, 10).map((entry, index) => (
                <li key={index}>{entry}</li>
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
