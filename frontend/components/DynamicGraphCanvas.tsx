"use client";

import dynamic from 'next/dynamic';
import type { GraphPayload } from "../types/graph";

interface GraphCanvasProps {
  graphData: GraphPayload | null;
  highlightedNodes: string[];
  onNodeClick?: (nodeId: string) => void;
  onEdgeClick?: (edgeId: string) => void;
}

const GraphCanvas = dynamic(() => import('./GraphCanvas'), {
  ssr: false,
  loading: () => <div>Loading graph visualization...</div>
});

const DynamicGraphCanvas: React.FC<GraphCanvasProps> = (props) => {
  return <GraphCanvas {...props} />;
};

export default DynamicGraphCanvas;