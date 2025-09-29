"use client";

import { useEffect, useMemo, useRef } from "react";
import Graph from "graphology";
import forceLayout from "graphology-layout-forceatlas2";
import Sigma from "sigma";
import type { GraphPayload } from "../types/graph";

interface GraphCanvasProps {
  graphData: GraphPayload | null;
  highlightNodes?: string[];
  className?: string;
}

function pickColor(labels: string[]): string {
  if (!labels.length) return "#2f80ed";
  if (labels.includes("Windows")) return "#0ea5e9";
  if (labels.includes("Linux")) return "#22c55e";
  if (labels.includes("Critical")) return "#ef4444";
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

export default function GraphCanvas({ graphData, highlightNodes = [], className }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const rendererRef = useRef<Sigma | null>(null);
  const graph = useMemo(() => {
    if (!graphData) return null;
    const g = new Graph({ multi: true });
    graphData.nodes.forEach((node) => {
      if (g.hasNode(node.id)) return;
      g.addNode(node.id, {
        ...node.attrs,
        label: (node.attrs?.name as string) ?? node.id,
        size: Number(node.attrs?.size ?? 7),
        color: pickColor(node.labels),
        x: Number(node.attrs?.x ?? Math.random()),
        y: Number(node.attrs?.y ?? Math.random())
      });
    });
    graphData.edges.forEach((edge) => {
      if (g.hasEdge(edge.id)) return;
      const attributes = {
        ...edge.attrs,
        label: edge.type,
        size: Number(edge.attrs?.width ?? 1),
        color: "#94a3b8",
        type: mapEdgeTypeToSigmaType(edge.type),
        originalType: edge.type
      };
      g.addEdgeWithKey(edge.id, edge.source, edge.target, attributes);
    });
    return g;
  }, [graphData]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !graph) return;

    const renderer = new Sigma(graph, container, {
      renderLabels: true,
      enableEdgeEvents: true,
      defaultNodeType: "circle",
      defaultEdgeType: "arrow"
    });

    rendererRef.current = renderer;

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
          slowDown: 2
        }
      });
    }

    return () => {
      renderer.kill();
      rendererRef.current = null;
    };
  }, [graph]);

  useEffect(() => {
    const renderer = rendererRef.current;
    if (!renderer || !graph) return;

    const highlighted = new Set(highlightNodes);
    renderer.setSetting("nodeReducer", (nodeKey, data) => {
      const isHighlighted = highlighted.has(nodeKey);
      return {
        ...data,
        color: isHighlighted ? "#f97316" : data.color,
        zIndex: isHighlighted ? 1 : 0,
        size: isHighlighted ? Number(data.size ?? 7) * 1.4 : data.size
      };
    });

    renderer.refresh();
  }, [highlightNodes, graph]);

  return <div ref={containerRef} className={className} style={{ width: "100%", height: "100%" }} />;
}
