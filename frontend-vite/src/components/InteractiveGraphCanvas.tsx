import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { ZoomIn, ZoomOut, Maximize2, Grid3x3, Circle, Shuffle, X, Info } from "lucide-react";
import Graph from "graphology";
import forceLayout from "graphology-layout-forceatlas2";
import Sigma from "sigma";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { ErrorBoundary, GraphErrorFallback } from "./ErrorBoundary";
import type { GraphPayload } from "../types/graph";

interface GraphCanvasProps {
  graphData: GraphPayload | null;
  highlightNodes?: string[];
  className?: string;
  onNodeClick?: (nodeId: string, nodeData: any) => void;
  onEdgeClick?: (edgeId: string, edgeData: any) => void;
  showMiniMap?: boolean;
}

interface GraphSettings {
  layout: "force" | "circular" | "grid";
  showLabels: boolean;
  enableInteraction: boolean;
  nodeSize: number;
  edgeSize: number;
}

function pickColor(labels: string[]): string {
  if (!labels.length) return "#60a5fa";
  if (labels.includes("Windows")) return "#0ea5e9";
  if (labels.includes("Linux")) return "#22c55e";
  if (labels.includes("Critical")) return "#ef4444";
  if (labels.includes("Server")) return "#8b5cf6";
  if (labels.includes("Database")) return "#f59e0b";
  return "#6366f1";
}

function mapEdgeTypeToSigmaType(edgeType: string): string {
  switch (edgeType) {
    case "allowed_tcp":
    case "allowed_udp":
    case "network_connection":
      return "arrow";
    case "contains":
    case "parent_child":
      return "line";
    case "encrypted":
    case "secure":
      return "curve";
    default:
      return "arrow";
  }
}

function GraphCanvasCore({
  graphData,
  highlightNodes = [],
  className,
  onNodeClick,
  onEdgeClick,
  showMiniMap = false
}: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const rendererRef = useRef<Sigma | null>(null);
  const [settings, setSettings] = useState<GraphSettings>({
    layout: "force",
    showLabels: true,
    enableInteraction: true,
    nodeSize: 7,
    edgeSize: 1,
  });
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [graphError, setGraphError] = useState<Error | null>(null);
  const [zoom, setZoom] = useState(1);

  const graph = useMemo(() => {
    try {
      if (!graphData) return null;

      const g = new Graph({ multi: true });

      graphData.nodes.forEach((node) => {
        if (g.hasNode(node.id)) return;
        g.addNode(node.id, {
          ...node.attrs,
          label: (node.attrs?.name as string) ?? node.id,
          size: Number(node.attrs?.size ?? settings.nodeSize),
          color: pickColor(node.labels),
          originalColor: pickColor(node.labels),
          x: Number(node.attrs?.x ?? Math.random() * 100),
          y: Number(node.attrs?.y ?? Math.random() * 100),
          labels: node.labels,
        });
      });

      graphData.edges.forEach((edge) => {
        if (g.hasEdge(edge.id)) return;
        try {
          const attributes = {
            ...edge.attrs,
            label: edge.type,
            size: Number(edge.attrs?.width ?? settings.edgeSize),
            color: "#64748b",
            originalColor: "#64748b",
            type: mapEdgeTypeToSigmaType(edge.type),
            originalType: edge.type,
          };
          g.addEdgeWithKey(edge.id, edge.source, edge.target, attributes);
        } catch (error) {
          console.warn(`Failed to add edge ${edge.id}:`, error);
        }
      });

      return g;
    } catch (error) {
      setGraphError(error as Error);
      return null;
    }
  }, [graphData, settings.nodeSize, settings.edgeSize]);

  const applyLayout = useCallback((graph: Graph) => {
    if (settings.layout === "force") {
      const shouldRunLayout = !graph.nodes().every((nodeId) => {
        const node = graph.getNodeAttributes(nodeId);
        return typeof node.x === "number" && typeof node.y === "number";
      });

      if (shouldRunLayout) {
        forceLayout.assign(graph, {
          iterations: 200,
          settings: {
            gravity: 1,
            adjustSizes: true,
            outboundAttractionDistribution: true,
            slowDown: 2,
          },
        });
      }
    } else if (settings.layout === "circular") {
      const nodes = graph.nodes();
      const center = { x: 50, y: 50 };
      const radius = Math.min(40, Math.max(10, nodes.length * 2));

      nodes.forEach((nodeId, index) => {
        const angle = (2 * Math.PI * index) / nodes.length;
        graph.setNodeAttribute(nodeId, "x", center.x + radius * Math.cos(angle));
        graph.setNodeAttribute(nodeId, "y", center.y + radius * Math.sin(angle));
      });
    } else if (settings.layout === "grid") {
      const nodes = graph.nodes();
      const gridSize = Math.ceil(Math.sqrt(nodes.length));

      nodes.forEach((nodeId, index) => {
        const row = Math.floor(index / gridSize);
        const col = index % gridSize;
        graph.setNodeAttribute(nodeId, "x", col * 15);
        graph.setNodeAttribute(nodeId, "y", row * 15);
      });
    }
  }, [settings.layout]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !graph) return;

    try {
      if (rendererRef.current) {
        rendererRef.current.kill();
        rendererRef.current = null;
      }

      const renderer = new Sigma(graph, container, {
        renderLabels: settings.showLabels,
        enableEdgeEvents: true,
        defaultNodeType: "circle",
        defaultEdgeType: "arrow",
        allowInvalidContainer: true,
      });

      rendererRef.current = renderer;
      applyLayout(graph);

      if (settings.enableInteraction) {
        renderer.on("clickNode", ({ node }) => {
          setSelectedNode(node);
          const nodeData = graph.getNodeAttributes(node);
          onNodeClick?.(node, nodeData);
        });

        renderer.on("clickEdge", ({ edge }) => {
          const edgeData = graph.getEdgeAttributes(edge);
          onEdgeClick?.(edge, edgeData);
        });

        renderer.on("clickStage", () => {
          setSelectedNode(null);
        });
      }

      // Update zoom state
      renderer.getCamera().on("updated", () => {
        setZoom(renderer.getCamera().ratio);
      });

      return () => {
        renderer.kill();
        rendererRef.current = null;
      };
    } catch (error) {
      setGraphError(error as Error);
    }
  }, [graph, settings, applyLayout, onNodeClick, onEdgeClick]);

  useEffect(() => {
    const renderer = rendererRef.current;
    if (!renderer || !graph) return;

    const highlighted = new Set(highlightNodes);
    const selected = selectedNode ? new Set([selectedNode]) : new Set();

    try {
      renderer.setSetting("nodeReducer", (nodeKey, data) => {
        const isHighlighted = highlighted.has(nodeKey);
        const isSelected = selected.has(nodeKey);

        let color = data.originalColor || data.color;
        let size = Number(data.size ?? settings.nodeSize);
        let zIndex = 0;

        if (isSelected) {
          color = "#f43f5e";
          size *= 1.6;
          zIndex = 2;
        } else if (isHighlighted) {
          color = "#f97316";
          size *= 1.4;
          zIndex = 1;
        }

        return { ...data, color, size, zIndex };
      });

      renderer.setSetting("edgeReducer", (edgeKey, data) => {
        const source = graph.source(edgeKey);
        const target = graph.target(edgeKey);
        const isConnected = highlighted.has(source) || highlighted.has(target) ||
                           selected.has(source) || selected.has(target);

        return {
          ...data,
          color: isConnected ? "#f97316" : (data.originalColor || data.color),
          size: isConnected ? Number(data.size ?? settings.edgeSize) * 1.5 : data.size,
        };
      });

      renderer.refresh();
    } catch (error) {
      console.warn("Error updating node/edge reducers:", error);
    }
  }, [highlightNodes, selectedNode, graph, settings.nodeSize, settings.edgeSize]);

  const handleZoomIn = () => {
    const camera = rendererRef.current?.getCamera();
    if (camera) {
      camera.animatedZoom({ duration: 300 });
    }
  };

  const handleZoomOut = () => {
    const camera = rendererRef.current?.getCamera();
    if (camera) {
      camera.animatedUnzoom({ duration: 300 });
    }
  };

  const handleResetView = () => {
    const camera = rendererRef.current?.getCamera();
    if (camera) {
      camera.animatedReset({ duration: 300 });
    }
  };

  if (graphError) {
    return (
      <GraphErrorFallback
        error={graphError}
        onRetry={() => setGraphError(null)}
      />
    );
  }

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center p-8">
        <div className="h-16 w-16 rounded-full bg-muted flex items-center justify-center mb-4">
          <Grid3x3 className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold mb-2">No Graph Data</h3>
        <p className="text-sm text-muted-foreground max-w-sm">
          Upload a graph JSON file or load the sample graph to visualize your network.
        </p>
      </div>
    );
  }

  return (
    <div className={cn("graph-canvas-container relative", className)}>
      {/* Top Controls */}
      <div className="absolute top-4 left-4 z-10 flex flex-col gap-2">
        <Card className="glass-panel">
          <CardContent className="p-3 space-y-3">
            <div>
              <label className="text-xs font-medium mb-2 block">Layout</label>
              <div className="flex gap-1">
                <Button
                  size="sm"
                  variant={settings.layout === "force" ? "default" : "outline"}
                  onClick={() => setSettings(s => ({ ...s, layout: "force" }))}
                  className="flex-1"
                >
                  <Shuffle className="h-3 w-3" />
                </Button>
                <Button
                  size="sm"
                  variant={settings.layout === "circular" ? "default" : "outline"}
                  onClick={() => setSettings(s => ({ ...s, layout: "circular" }))}
                  className="flex-1"
                >
                  <Circle className="h-3 w-3" />
                </Button>
                <Button
                  size="sm"
                  variant={settings.layout === "grid" ? "default" : "outline"}
                  onClick={() => setSettings(s => ({ ...s, layout: "grid" }))}
                  className="flex-1"
                >
                  <Grid3x3 className="h-3 w-3" />
                </Button>
              </div>
            </div>

            <Separator />

            <div>
              <label className="flex items-center gap-2 text-xs cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.showLabels}
                  onChange={(e) => setSettings(s => ({ ...s, showLabels: e.target.checked }))}
                  className="rounded"
                />
                Show Labels
              </label>
            </div>
          </CardContent>
        </Card>

        <Card className="glass-panel">
          <CardContent className="p-2 space-y-1">
            <Button
              size="sm"
              variant="ghost"
              onClick={handleZoomIn}
              className="w-full justify-start"
            >
              <ZoomIn className="h-4 w-4 mr-2" />
              Zoom In
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={handleZoomOut}
              className="w-full justify-start"
            >
              <ZoomOut className="h-4 w-4 mr-2" />
              Zoom Out
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={handleResetView}
              className="w-full justify-start"
            >
              <Maximize2 className="h-4 w-4 mr-2" />
              Reset
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Graph Stats */}
      <div className="absolute top-4 right-4 z-10">
        <Card className="glass-panel">
          <CardContent className="p-3 flex items-center gap-3">
            <div className="flex items-center gap-2">
              <Badge variant="secondary" className="text-xs">
                {graphData.nodes.length} nodes
              </Badge>
              <Badge variant="secondary" className="text-xs">
                {graphData.edges.length} edges
              </Badge>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Canvas */}
      <div ref={containerRef} className="graph-canvas" style={{ width: "100%", height: "100%" }} />

      {/* Selected Node Panel */}
      {selectedNode && graph && (
        <Card className="absolute bottom-4 right-4 z-10 glass-panel min-w-[280px] max-w-xs">
          <CardContent className="p-4">
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-2">
                <Info className="h-4 w-4 text-primary" />
                <h4 className="font-semibold text-sm">Node Details</h4>
              </div>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setSelectedNode(null)}
                className="h-6 w-6 p-0"
              >
                <X className="h-3 w-3" />
              </Button>
            </div>

            <div className="space-y-2 text-sm">
              <div>
                <span className="text-muted-foreground text-xs">ID:</span>
                <p className="font-mono text-xs break-all mt-1">{selectedNode}</p>
              </div>

              <div>
                <span className="text-muted-foreground text-xs">Labels:</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {(graph.getNodeAttribute(selectedNode, "labels") as string[] || []).map((label) => (
                    <Badge key={label} variant="outline" className="text-xs">
                      {label}
                    </Badge>
                  ))}
                </div>
              </div>

              <div>
                <span className="text-muted-foreground text-xs">Connections:</span>
                <p className="mt-1">
                  <Badge variant="info" className="text-xs">
                    {graph.degree(selectedNode)} edges
                  </Badge>
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default function InteractiveGraphCanvas(props: GraphCanvasProps) {
  return (
    <ErrorBoundary
      fallback={<GraphErrorFallback error={undefined} onRetry={() => window.location.reload()} />}
    >
      <GraphCanvasCore {...props} />
    </ErrorBoundary>
  );
}