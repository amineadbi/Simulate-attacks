"use client";

import dynamic from 'next/dynamic';
import type { GraphPayload } from "../types/graph";

interface GraphCanvasProps {
  graphData: GraphPayload | null;
  highlightNodes: string[];
  onNodeClick?: (nodeId: string, nodeData: any) => void;
  onEdgeClick?: (edgeId: string, edgeData: any) => void;
  layout?: 'force' | 'circular' | 'random';
  enablePhysics?: boolean;
  showMiniMap?: boolean;
}

const InteractiveGraphCanvas = dynamic(() => import('./InteractiveGraphCanvas'), {
  ssr: false,
  loading: () => <div className="loading-graph">Loading interactive graph...</div>
});

const DynamicInteractiveGraphCanvas: React.FC<GraphCanvasProps> = (props) => {
  return <InteractiveGraphCanvas {...props} />;
};

export default DynamicInteractiveGraphCanvas;