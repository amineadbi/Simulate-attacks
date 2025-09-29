

import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import Graph from "graphology";
import forceLayout from "graphology-layout-forceatlas2";
import Sigma from "sigma";
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
  if (!labels.length) return "#2f80ed";
  if (labels.includes("Windows")) return "#0ea5e9";
  if (labels.includes("Linux")) return "#22c55e";
  if (labels.includes("Critical")) return "#ef4444";
  if (labels.includes("Server")) return "#8b5cf6";
  if (labels.includes("Database")) return "#f59e0b";
  return "#6366f1";
}

function mapEdgeTypeToSigmaType(edgeType: string): string {
  // Map custom edge types to valid Sigma.js edge types
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
      return "arrow"; // Default fallback
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
            color: "#94a3b8",
            originalColor: "#94a3b8",
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
      // Clean up previous renderer
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

      // Apply layout
      applyLayout(graph);

      // Event handlers
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

      return () => {
        renderer.kill();
        rendererRef.current = null;
      };
    } catch (error) {
      setGraphError(error as Error);
    }
  }, [graph, settings, applyLayout, onNodeClick, onEdgeClick]);

  // Handle node highlighting
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
          color = "#ff6b6b";
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

  if (graphError) {
    return (
      <GraphErrorFallback
        error={graphError}
        onRetry={() => setGraphError(null)}
      />
    );
  }

  return (
    <div className={`graph-canvas-container ${className || ""}`}>
      <div className="graph-controls">
        <select
          value={settings.layout}
          onChange={(e) => setSettings(s => ({ ...s, layout: e.target.value as any }))}
        >
          <option value="force">Force Layout</option>
          <option value="circular">Circular Layout</option>
          <option value="grid">Grid Layout</option>
        </select>

        <label>
          <input
            type="checkbox"
            checked={settings.showLabels}
            onChange={(e) => setSettings(s => ({ ...s, showLabels: e.target.checked }))}
          />
          Show Labels
        </label>

        <label>
          Node Size:
          <input
            type="range"
            min="3"
            max="15"
            value={settings.nodeSize}
            onChange={(e) => setSettings(s => ({ ...s, nodeSize: Number(e.target.value) }))}
          />
        </label>
      </div>

      <div ref={containerRef} className="graph-canvas" style={{ width: "100%", height: "100%" }} />

      {selectedNode && (
        <div className="node-details-panel">
          <h4>Node Details</h4>
          <p><strong>ID:</strong> {selectedNode}</p>
          {graph && (
            <div>
              <p><strong>Labels:</strong> {graph.getNodeAttribute(selectedNode, "labels")?.join(", ") || "None"}</p>
              <p><strong>Connections:</strong> {graph.degree(selectedNode)}</p>
            </div>
          )}
          <button onClick={() => setSelectedNode(null)}>Close</button>
        </div>
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