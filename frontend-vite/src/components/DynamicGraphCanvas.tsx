

import GraphCanvas from './GraphCanvas';
import type { GraphPayload } from "../types/graph";

interface GraphCanvasProps {
  graphData: GraphPayload | null;
  highlightedNodes: string[];
  onNodeClick?: (nodeId: string) => void;
  onEdgeClick?: (edgeId: string) => void;
}

const DynamicGraphCanvas: React.FC<GraphCanvasProps> = (props) => {
  return <GraphCanvas {...props} />;
};

export default DynamicGraphCanvas;