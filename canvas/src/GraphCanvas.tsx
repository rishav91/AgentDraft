import "@xyflow/react/dist/style.css";

import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Connection,
  type NodeMouseHandler,
  type NodeTypes,
} from "@xyflow/react";
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
  mode?: "view" | "edit";
  selectedNodeId?: string | null;
  onConnect?: (connection: Connection) => void;
  onNodeClick?: (nodeId: string) => void;
};

// mode="view" (the default) reproduces Phase 2.1's exact read-only behavior:
// nodes can be dragged to detangle the layout, nothing writes back to the
// schema. mode="edit" (Phase 2.2) additionally allows dragging a connection
// to wire a direct edge, and clicking a node to select it for the Inspector.
export function GraphCanvas({
  structure,
  mode = "view",
  selectedNodeId = null,
  onConnect,
  onNodeClick,
}: GraphCanvasProps) {
  const { nodes: baseNodes, edges } = useMemo(() => layoutGraph(structure), [structure]);
  const nodes = useMemo(
    () => baseNodes.map((node) => ({ ...node, selected: node.id === selectedNodeId })),
    [baseNodes, selectedNodeId],
  );

  const handleNodeClick: NodeMouseHandler | undefined =
    mode === "edit" && onNodeClick ? (_, node) => onNodeClick(node.id) : undefined;

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      nodesConnectable={mode === "edit"}
      onConnect={mode === "edit" ? onConnect : undefined}
      onNodeClick={handleNodeClick}
      fitView
    >
      <Background />
      <Controls showInteractive={false} />
      <MiniMap pannable zoomable />
    </ReactFlow>
  );
}
