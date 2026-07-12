import "@xyflow/react/dist/style.css";

import { Background, Controls, MiniMap, ReactFlow, type NodeTypes } from "@xyflow/react";
import { useMemo } from "react";

import { layoutGraph } from "./layout";
import { EndpointNode } from "./nodes/EndpointNode";
import { SchemaNode } from "./nodes/SchemaNode";
import type { GraphStructure } from "./types";

const nodeTypes: NodeTypes = {
  schemaNode: SchemaNode,
  endpointNode: EndpointNode,
};

type GraphCanvasProps = {
  structure: GraphStructure;
};

// Read-only for Phase 2.1 (ROADMAP): nodes can be dragged to detangle the
// layout, but nothing here writes back to the schema - that's Phase 2.2.
export function GraphCanvas({ structure }: GraphCanvasProps) {
  const { nodes, edges } = useMemo(() => layoutGraph(structure), [structure]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      nodesConnectable={false}
      fitView
    >
      <Background />
      <Controls showInteractive={false} />
      <MiniMap pannable zoomable />
    </ReactFlow>
  );
}
