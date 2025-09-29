declare module "graphology-layout-forceatlas2" {
  import Graph from "graphology";

  interface ForceAtlas2Settings {
    gravity?: number;
    scalingRatio?: number;
    adjustSizes?: boolean;
    strongGravityMode?: boolean;
    slowDown?: number;
    outboundAttractionDistribution?: boolean;
  }

  interface AssignOptions {
    iterations?: number;
    settings?: ForceAtlas2Settings;
  }

  interface ForceAtlas2 {
    (graph: Graph, options?: AssignOptions): Record<string, { x: number; y: number }>;
    assign(graph: Graph, options?: AssignOptions): void;
  }

  const forceAtlas2: ForceAtlas2;
  export default forceAtlas2;
}
