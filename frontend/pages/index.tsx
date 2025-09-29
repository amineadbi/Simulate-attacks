"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import ChatPanel from "../components/ChatPanel";
import ConnectionIndicator from "../components/ConnectionIndicator";
import CypherQueryBar from "../components/CypherQueryBar";
import DynamicInteractiveGraphCanvas from "../components/DynamicInteractiveGraphCanvas";
import GraphUploader from "../components/GraphUploader";
import ScenarioControls from "../components/ScenarioControls";
import OptimizedLogPanel from "../components/OptimizedLogPanel";
import SimulationPanel from "../components/SimulationPanel";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { LoadingState, ConnectionStatus } from "../components/LoadingStates";
import { useAppState } from "../hooks/useAppState";
import { useWebSocketWithRetry } from "../hooks/useWebSocketWithRetry";
import { useDebounce, usePerformanceMonitor } from "../lib/performance";

function generateId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2, 11);
}

export default function HomePage() {
  const { state, handlers } = useAppState();
  const { start, end } = usePerformanceMonitor("HomePage render");
  const [simulationPanelVisible, setSimulationPanelVisible] = useState(false);

  // Debounced handlers for performance
  const debouncedHandleStreamEvent = useDebounce(handlers.handleStreamEvent, 50);
  const debouncedHandleStatusChange = useDebounce(handlers.handleStatusChange, 100);

  const { status: connectionStatus, metrics, sendMessage, retryCount } = useWebSocketWithRetry({
    onEvent: debouncedHandleStreamEvent,
    onStatusChange: debouncedHandleStatusChange,
    maxRetries: 5,
  });

  useEffect(() => {
    start();
    return () => {
      end();
    };
  }, [start, end]);

  // Request initial graph data when connected
  useEffect(() => {
    if (connectionStatus === "open") {
      sendMessage({ type: "graph.request", request: "full" });
    }
  }, [connectionStatus, sendMessage]);

  // Chat handler
  const handleSendChat = useCallback(
    (text: string) => {
      if (!text.trim()) return;
      handlers.setWaitingForAgent(true);
      sendMessage({ type: "agent.command", command: "chat", payload: { text } });
    },
    [sendMessage, handlers.setWaitingForAgent]
  );

  // Node interaction handlers
  const handleNodeClick = useCallback((nodeId: string, nodeData: any) => {
    console.log("Node clicked:", nodeId, nodeData);
    // Could add node detail panel or other interactions here
  }, []);

  const handleEdgeClick = useCallback((edgeId: string, edgeData: any) => {
    console.log("Edge clicked:", edgeId, edgeData);
    // Could add edge detail panel or other interactions here
  }, []);

  // Scenario status summary with loading state
  const scenarioSummary = useMemo(() => {
    if (!state.scenarioStatus) return "No scenario run yet";
    const { status, jobId } = state.scenarioStatus;
    return `Job ${jobId} is ${status}`;
  }, [state.scenarioStatus]);

  // Connection status for UI
  const connectionState = useMemo(() => {
    const statusMap = {
      idle: "disconnected" as const,
      connecting: "connecting" as const,
      open: "connected" as const,
      retrying: "connecting" as const,
      closed: "disconnected" as const,
      error: "error" as const,
    };
    return statusMap[connectionStatus];
  }, [connectionStatus]);

  const hasData = state.graphData && state.graphData.nodes.length > 0;

  return (
    <ErrorBoundary>
      <div className="layout">
        <header className="header">
          <div className="headline">
            <h1>Graph Scenario Workbench</h1>
            <div className="connection-info">
              <ConnectionStatus
                status={connectionState}
                message={retryCount > 0 ? `Retry attempt ${retryCount}` : undefined}
              />
              <ConnectionIndicator
                state={connectionStatus}
                lastConnectedAt={metrics.lastConnectedAt}
              />
              <button
                onClick={() => setSimulationPanelVisible(!simulationPanelVisible)}
                className="ml-4 px-3 py-1 bg-blue-500 text-white text-sm rounded hover:bg-blue-600 transition-colors"
              >
                🎯 Simulations
              </button>
            </div>
          </div>
          <p className="subtitle">Upload, inspect, and exercise your network graph in real time.</p>
        </header>

        <main className="main">
          <section className="left-pane">
            <ErrorBoundary fallback={<div>Chat panel failed to load</div>}>
              <LoadingState
                isLoading={connectionStatus === "connecting"}
                error={connectionStatus === "error" ? "Failed to connect to agent" : null}
                loadingText="Connecting to agent..."
                retryAction={() => window.location.reload()}
              >
                <ChatPanel
                  messages={state.chatMessages}
                  connectionState={connectionStatus}
                  onSend={handleSendChat}
                  disabled={connectionStatus !== "open"}
                  isWaitingForAgent={state.isWaitingForAgent}
                />
              </LoadingState>
            </ErrorBoundary>

            <ErrorBoundary fallback={<div>Graph uploader failed to load</div>}>
              <GraphUploader onGraphLoaded={handlers.handleGraphLoadedEvent} />
            </ErrorBoundary>

            <ErrorBoundary fallback={<div>Cypher query bar failed to load</div>}>
              <CypherQueryBar onResult={handlers.handleCypherResultEvent} />
            </ErrorBoundary>

            <ErrorBoundary fallback={<div>Scenario controls failed to load</div>}>
              <ScenarioControls
                connectionStatus={connectionStatus}
                latestStatus={state.scenarioStatus}
                sendMessage={sendMessage}
                onScenarioStarted={(status) => {
                  handlers.handleStreamEvent({
                    id: generateId(),
                    type: "scenario.status",
                    createdAt: new Date().toISOString(),
                    payload: status,
                  });
                }}
                onScenarioError={(message) => {
                  handlers.handleStreamEvent({
                    id: generateId(),
                    type: "agent.log",
                    createdAt: new Date().toISOString(),
                    payload: { message: `Scenario failed to start: ${message}` },
                    level: "error",
                  });
                }}
              />
            </ErrorBoundary>

            <ErrorBoundary fallback={<div>Activity log failed to load</div>}>
              <OptimizedLogPanel
                logEntries={state.logEntries}
                maxHeight={400}
              />
            </ErrorBoundary>

            <section className="result-panel">
              <h2>Scenario Summary</h2>
              <p>{scenarioSummary}</p>
              {(state.scenarioResults as any) && (
                <details>
                  <summary>Inspect Raw Results</summary>
                  <pre>{JSON.stringify(state.scenarioResults, null, 2)}</pre>
                </details>
              )}
            </section>

            {state.cypherResult && (
              <section className="result-panel">
                <h2>Cypher Result (latest)</h2>
                <details>
                  <summary>Show {state.cypherResult.records?.length || 0} records</summary>
                  <pre>{JSON.stringify(state.cypherResult, null, 2)}</pre>
                </details>
              </section>
            )}
          </section>

          <section className="right-pane">
            <ErrorBoundary fallback={<div>Graph visualization failed to load</div>}>
              <LoadingState
                isLoading={!hasData && connectionStatus === "connecting"}
                error={null}
                loadingText="Loading graph data..."
              >
                <DynamicInteractiveGraphCanvas
                  graphData={state.graphData}
                  highlightNodes={state.highlightedNodes}
                  onNodeClick={handleNodeClick}
                  onEdgeClick={handleEdgeClick}
                  showMiniMap={false}
                />
              </LoadingState>
            </ErrorBoundary>
          </section>
        </main>

        {/* Simulation Panel */}
        <SimulationPanel
          isVisible={simulationPanelVisible}
          onClose={() => setSimulationPanelVisible(false)}
        />
      </div>
    </ErrorBoundary>
  );
}