import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, MessageSquare, Network, Play, Terminal } from "lucide-react";
import ChatPanel from "./components/ChatPanel";
import ConnectionIndicator from "./components/ConnectionIndicator";
import CypherQueryBar from "./components/CypherQueryBar";
import DynamicInteractiveGraphCanvas from "./components/DynamicInteractiveGraphCanvas";
import GraphUploader from "./components/GraphUploader";
import ScenarioControls from "./components/ScenarioControls";
import OptimizedLogPanel from "./components/OptimizedLogPanel";
import SimulationPanel from "./components/SimulationPanel";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { LoadingState, ConnectionStatus } from "./components/LoadingStates";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAppState } from "./hooks/useAppState";
import { useWebSocketWithRetry } from "./hooks/useWebSocketWithRetry";
import { useDebounce, usePerformanceMonitor } from "./lib/performance";

function generateId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2, 11);
}

export default function App() {
  const { state, handlers } = useAppState();
  const { start, end } = usePerformanceMonitor("HomePage render");
  const [simulationPanelVisible, setSimulationPanelVisible] = useState(false);
  const [activeTab, setActiveTab] = useState("chat");

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

  useEffect(() => {
    if (connectionStatus === "open") {
      sendMessage({ type: "graph.request", request: "full" });
    }
  }, [connectionStatus, sendMessage]);

  const handleSendChat = useCallback(
    (text: string) => {
      if (!text.trim()) return;
      handlers.setWaitingForAgent(true);
      sendMessage({ type: "agent.command", command: "chat", payload: { text } });
    },
    [sendMessage, handlers.setWaitingForAgent]
  );

  const handleNodeClick = useCallback((nodeId: string, nodeData: any) => {
    console.log("Node clicked:", nodeId, nodeData);
  }, []);

  const handleEdgeClick = useCallback((edgeId: string, edgeData: any) => {
    console.log("Edge clicked:", edgeId, edgeData);
  }, []);

  const scenarioSummary = useMemo(() => {
    if (!state.scenarioStatus) return "No scenario run yet";
    const { status, jobId } = state.scenarioStatus;
    return `Job ${jobId} is ${status}`;
  }, [state.scenarioStatus]);

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
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
        {/* Header */}
        <header className="border-b border-white/10 bg-card/30 backdrop-blur-xl sticky top-0 z-50">
          <div className="container mx-auto px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                    <Network className="h-6 w-6 text-white" />
                  </div>
                  <div>
                    <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                      Graph Scenario Workbench
                    </h1>
                    <p className="text-xs text-muted-foreground">
                      AI-Powered Network Analysis & Simulation
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <ConnectionStatus
                  status={connectionState}
                  message={retryCount > 0 ? `Retry ${retryCount}` : undefined}
                />
                <ConnectionIndicator
                  state={connectionStatus}
                  lastConnectedAt={metrics.lastConnectedAt}
                />
                <Button
                  onClick={() => setSimulationPanelVisible(!simulationPanelVisible)}
                  variant="outline"
                  size="sm"
                  className="gap-2"
                >
                  <Play className="h-4 w-4" />
                  Simulations
                </Button>
              </div>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="container mx-auto px-6 py-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[calc(100vh-140px)]">
            {/* Left Sidebar - Tabs */}
            <div className="lg:col-span-1">
              <Card className="h-full glass-panel">
                <Tabs defaultValue="chat" value={activeTab} onValueChange={setActiveTab} className="h-full flex flex-col">
                  <div className="border-b border-white/10 px-6 pt-6">
                    <TabsList className="w-full grid grid-cols-4 gap-2 bg-secondary/50">
                      <TabsTrigger value="chat" className="gap-1 text-xs">
                        <MessageSquare className="h-3 w-3" />
                        Chat
                      </TabsTrigger>
                      <TabsTrigger value="scenario" className="gap-1 text-xs">
                        <Play className="h-3 w-3" />
                        Scenario
                      </TabsTrigger>
                      <TabsTrigger value="query" className="gap-1 text-xs">
                        <Terminal className="h-3 w-3" />
                        Query
                      </TabsTrigger>
                      <TabsTrigger value="logs" className="gap-1 text-xs">
                        <Activity className="h-3 w-3" />
                        Logs
                      </TabsTrigger>
                    </TabsList>
                  </div>

                  <div className="flex-1 overflow-auto">
                    <TabsContent value="chat" className="m-0 h-full">
                      <ErrorBoundary fallback={<div className="p-4">Chat panel failed to load</div>}>
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
                    </TabsContent>

                    <TabsContent value="scenario" className="m-0 p-6 space-y-4">
                      <ErrorBoundary fallback={<div>Graph uploader failed to load</div>}>
                        <GraphUploader onGraphLoaded={handlers.handleGraphLoadedEvent} />
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
                              payload: { message: `Scenario failed: ${message}` },
                              level: "error",
                            });
                          }}
                        />
                      </ErrorBoundary>

                      <Card className="glass-panel">
                        <CardContent className="pt-6">
                          <h3 className="text-sm font-semibold mb-2">Scenario Status</h3>
                          <p className="text-sm text-muted-foreground">{scenarioSummary}</p>
                          {(state.scenarioResults as any) && (
                            <details className="mt-4">
                              <summary className="cursor-pointer text-sm text-primary hover:underline">
                                View Results
                              </summary>
                              <pre className="mt-2 text-xs bg-muted/50 p-3 rounded-md overflow-auto max-h-60">
                                {JSON.stringify(state.scenarioResults, null, 2)}
                              </pre>
                            </details>
                          )}
                        </CardContent>
                      </Card>
                    </TabsContent>

                    <TabsContent value="query" className="m-0 p-6 space-y-4">
                      <ErrorBoundary fallback={<div>Cypher query bar failed to load</div>}>
                        <CypherQueryBar onResult={handlers.handleCypherResultEvent} />
                      </ErrorBoundary>

                      {state.cypherResult && (
                        <Card className="glass-panel">
                          <CardContent className="pt-6">
                            <div className="flex items-center justify-between mb-3">
                              <h3 className="text-sm font-semibold">Query Result</h3>
                              <Badge variant="secondary">
                                {state.cypherResult.records?.length || 0} records
                              </Badge>
                            </div>
                            <pre className="text-xs bg-muted/50 p-3 rounded-md overflow-auto max-h-96">
                              {JSON.stringify(state.cypherResult, null, 2)}
                            </pre>
                          </CardContent>
                        </Card>
                      )}
                    </TabsContent>

                    <TabsContent value="logs" className="m-0 p-6">
                      <ErrorBoundary fallback={<div>Activity log failed to load</div>}>
                        <OptimizedLogPanel
                          logEntries={state.logEntries}
                          maxHeight={600}
                        />
                      </ErrorBoundary>
                    </TabsContent>
                  </div>
                </Tabs>
              </Card>
            </div>

            {/* Right Side - Graph Visualization */}
            <div className="lg:col-span-2">
              <Card className="h-full glass-panel overflow-hidden">
                <ErrorBoundary fallback={<div className="p-4">Graph visualization failed to load</div>}>
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
              </Card>
            </div>
          </div>
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