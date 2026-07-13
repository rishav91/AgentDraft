import { MarkerType } from "@xyflow/react";
import dagre from "dagre";

import type { AppFlowEdge, AppFlowNode, EndpointNodeData, SchemaNodeData } from "./flowTypes";
import type { GraphStructure } from "./types";

const ARROW_MARKER = { type: MarkerType.ArrowClosed, width: 18, height: 18 } as const;

const NODE_WIDTH = 220;
// Exported so SelfLoopEdge can compute exact clearance above a node's real
// top edge, instead of guessing an offset from the handle's y (its center).
export const NODE_HEIGHT = 72;
const ENDPOINT_WIDTH = 90;
const ENDPOINT_HEIGHT = 36;

// Nodes referenced by edges (from/to/routes) that aren't in structure.nodes are the
// synthetic START/END sentinels - see agentdraft.compiler.schema_structure().
function endpointIds(structure: GraphStructure): Set<string> {
  const known = new Set(structure.nodes.map((node) => node.id));
  const endpoints = new Set<string>();
  for (const edge of structure.edges) {
    const targets = [edge.from, edge.to, ...(edge.routes ? Object.values(edge.routes) : [])];
    for (const id of targets) {
      if (id && !known.has(id)) endpoints.add(id);
    }
  }
  return endpoints;
}

export function layoutGraph(structure: GraphStructure): {
  nodes: AppFlowNode[];
  edges: AppFlowEdge[];
} {
  const graph = new dagre.graphlib.Graph();
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph({ rankdir: "LR", nodesep: 48, ranksep: 96 });

  for (const node of structure.nodes) {
    graph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  const endpoints = endpointIds(structure);
  for (const id of endpoints) {
    graph.setNode(id, { width: ENDPOINT_WIDTH, height: ENDPOINT_HEIGHT });
  }

  const edges: AppFlowEdge[] = [];
  let edgeCounter = 0;
  for (const edge of structure.edges) {
    if (edge.kind === "direct" && edge.to) {
      graph.setEdge(edge.from, edge.to);
      edges.push({
        id: `e${edgeCounter++}`,
        source: edge.from,
        target: edge.to,
        // React Flow's built-in edge types can't render a node pointing at
        // itself - their path math assumes source/target are different
        // nodes (see SelfLoopEdge.tsx).
        type: edge.from === edge.to ? "selfLoop" : "smoothstep",
        markerEnd: ARROW_MARKER,
      });
    } else if (edge.kind === "conditional" && edge.routes) {
      for (const [routeKey, target] of Object.entries(edge.routes)) {
        const isCappedFallback = edge.max_visits != null && routeKey === edge.fallback;
        graph.setEdge(edge.from, target);
        edges.push({
          id: `e${edgeCounter++}`,
          source: edge.from,
          target,
          type: edge.from === target ? "selfLoop" : "smoothstep",
          label: isCappedFallback ? `${routeKey} (after ${edge.max_visits})` : routeKey,
          data: { condition: edge.condition ?? "" },
          style: { strokeDasharray: "5 5" },
          markerEnd: ARROW_MARKER,
        });
      }
    }
  }

  dagre.layout(graph);

  const nodes: AppFlowNode[] = structure.nodes.map((node) => {
    const { x, y } = graph.node(node.id);
    const data: SchemaNodeData = {
      label: node.id,
      kind: node.kind,
      llmSummary: node.llm ? `${node.llm.provider}/${node.llm.model}` : null,
      handler: node.handler,
      tools: node.tools,
    };
    return {
      id: node.id,
      type: "schemaNode",
      position: { x: x - NODE_WIDTH / 2, y: y - NODE_HEIGHT / 2 },
      data,
    };
  });

  for (const id of endpoints) {
    const { x, y } = graph.node(id);
    const data: EndpointNodeData = { label: id };
    nodes.push({
      id,
      type: "endpointNode",
      position: { x: x - ENDPOINT_WIDTH / 2, y: y - ENDPOINT_HEIGHT / 2 },
      data,
    });
  }

  return { nodes, edges };
}
