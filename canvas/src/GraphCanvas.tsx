import "@xyflow/react/dist/style.css";

import {
  applyNodeChanges,
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Connection,
  type NodeChange,
  type NodeMouseHandler,
  type NodeTypes,
} from "@xyflow/react";
import { useEffect, useMemo, useState } from "react";

import type { AppFlowNode } from "./flowTypes";
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
  const { nodes: layoutNodes, edges } = useMemo(() => layoutGraph(structure), [structure]);

  // React Flow's `nodes` prop is fully controlled - without an onNodesChange
  // handler feeding drag deltas back in, dragging has no effect at all. Local
  // position state, resynced (data only, positions preserved) whenever the
  // structure's node/edge set changes, is what makes dragging actually stick.
  const [positionedNodes, setPositionedNodes] = useState<AppFlowNode[]>(layoutNodes);
  useEffect(() => {
    setPositionedNodes((current) => {
      const previousPositions = new Map(current.map((node) => [node.id, node.position]));
      return layoutNodes.map((node) => ({
        ...node,
        position: previousPositions.get(node.id) ?? node.position,
      }));
    });
  }, [layoutNodes]);

  const nodes = useMemo(
    () => positionedNodes.map((node) => ({ ...node, selected: node.id === selectedNodeId })),
    [positionedNodes, selectedNodeId],
  );

  const handleNodesChange = (changes: NodeChange[]) => {
    setPositionedNodes((current) => applyNodeChanges(changes, current) as AppFlowNode[]);
  };

  const handleNodeClick: NodeMouseHandler | undefined =
    mode === "edit" && onNodeClick ? (_, node) => onNodeClick(node.id) : undefined;

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      nodesDraggable
      nodesConnectable={mode === "edit"}
      onNodesChange={handleNodesChange}
      onConnect={mode === "edit" ? onConnect : undefined}
      onNodeClick={handleNodeClick}
      fitView
    >
      <Background />
      <Controls showInteractive={false} />
      <MiniMap pannable zoomable nodeColor="#94a3b8" maskColor="rgba(100, 116, 139, 0.25)" />
    </ReactFlow>
  );
}
