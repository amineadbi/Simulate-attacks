

import InteractiveGraphCanvas from './InteractiveGraphCanvas';
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

const DynamicInteractiveGraphCanvas: React.FC<GraphCanvasProps> = (props) => {
  return <InteractiveGraphCanvas {...props} />;
};

export default DynamicInteractiveGraphCanvas;