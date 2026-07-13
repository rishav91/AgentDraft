// Pure GraphStructure -> GraphStructure transitions backing the editor (FR-4.2).
// Kept framework-free so they're directly unit-testable (Phase 2.3).

import type { GraphEdge, GraphNode, GraphStructure } from "./types";

const RESERVED_IDS = new Set(["START", "END"]);

export function nextNodeId(structure: GraphStructure): string {
  const used = new Set([...structure.nodes.map((node) => node.id), ...RESERVED_IDS]);
  let n = structure.nodes.length + 1;
  while (used.has(`node_${n}`)) n += 1;
  return `node_${n}`;
}

export function addNode(structure: GraphStructure): GraphStructure {
  const newNode: GraphNode = {
    id: nextNodeId(structure),
    kind: "llm",
    llm: { provider: "", model: "", system: null },
    handler: null,
    tools: [],
  };
  return { ...structure, nodes: [...structure.nodes, newNode] };
}

function renameEdgeReference(edge: GraphEdge, oldId: string, newId: string): GraphEdge {
  const from = edge.from === oldId ? newId : edge.from;
  const to = edge.to === oldId ? newId : edge.to;
  const routes = edge.routes
    ? Object.fromEntries(
        Object.entries(edge.routes).map(([key, target]) => [
          key,
          target === oldId ? newId : target,
        ]),
      )
    : edge.routes;
  return { ...edge, from, to, routes };
}

export function updateNode(
  structure: GraphStructure,
  nodeId: string,
  patch: Partial<GraphNode>,
): GraphStructure {
  const renamedTo = patch.id && patch.id !== nodeId ? patch.id : null;

  const nodes = structure.nodes.map((node) =>
    node.id === nodeId ? { ...node, ...patch } : node,
  );
  const edges = renamedTo
    ? structure.edges.map((edge) => renameEdgeReference(edge, nodeId, renamedTo))
    : structure.edges;

  return { ...structure, nodes, edges };
}

export type RemoveNodeResult = {
  structure: GraphStructure;
  /** Human-readable summary of dangling references that were cleaned up elsewhere. */
  cleanups: string[];
};

export function removeNode(structure: GraphStructure, nodeId: string): RemoveNodeResult {
  const nodes = structure.nodes.filter((node) => node.id !== nodeId);
  const cleanups: string[] = [];
  const edges: GraphEdge[] = [];

  for (const edge of structure.edges) {
    if (edge.from === nodeId) {
      continue; // the deleted node's own outgoing edge goes with it, no separate cleanup note
    }
    if (edge.kind === "direct") {
      if (edge.to === nodeId) {
        cleanups.push(`removed edge ${edge.from} -> ${nodeId}`);
        continue;
      }
      edges.push(edge);
      continue;
    }
    const remainingRoutes = Object.fromEntries(
      Object.entries(edge.routes ?? {}).filter(([routeKey, target]) => {
        if (target !== nodeId) return true;
        cleanups.push(`removed route '${routeKey}' from ${edge.from} (targeted ${nodeId})`);
        return false;
      }),
    );
    if (Object.keys(remainingRoutes).length > 0) {
      edges.push({ ...edge, routes: remainingRoutes });
    } else {
      cleanups.push(`removed conditional routing from ${edge.from} (no routes left)`);
    }
  }

  return { structure: { ...structure, nodes, edges }, cleanups };
}

export function outgoingEdges(structure: GraphStructure, nodeId: string): GraphEdge[] {
  return structure.edges.filter((edge) => edge.from === nodeId);
}

export function setOutgoingDirect(
  structure: GraphStructure,
  nodeId: string,
  targets: string[],
): GraphStructure {
  const otherEdges = structure.edges.filter((edge) => edge.from !== nodeId);
  const newEdges: GraphEdge[] = targets.map((target) => ({
    from: nodeId,
    kind: "direct",
    to: target,
    condition: null,
    routes: null,
  }));
  return { ...structure, edges: [...otherEdges, ...newEdges] };
}

export function setOutgoingConditional(
  structure: GraphStructure,
  nodeId: string,
  condition: string,
  routes: Record<string, string>,
): GraphStructure {
  const otherEdges = structure.edges.filter((edge) => edge.from !== nodeId);
  const newEdge: GraphEdge = { from: nodeId, kind: "conditional", to: null, condition, routes };
  return { ...structure, edges: [...otherEdges, newEdge] };
}

export function clearOutgoing(structure: GraphStructure, nodeId: string): GraphStructure {
  return { ...structure, edges: structure.edges.filter((edge) => edge.from !== nodeId) };
}

/** Adds a direct target via drag-to-connect; no-ops if the source is already conditional. */
export function addDirectTarget(
  structure: GraphStructure,
  nodeId: string,
  target: string,
): GraphStructure {
  const existing = outgoingEdges(structure, nodeId);
  if (existing.some((edge) => edge.kind === "conditional")) {
    return structure;
  }
  const currentTargets = existing.map((edge) => edge.to).filter((to): to is string => to !== null);
  if (currentTargets.includes(target)) {
    return structure;
  }
  return setOutgoingDirect(structure, nodeId, [...currentTargets, target]);
}
