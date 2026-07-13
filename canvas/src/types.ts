// Mirrors agentdraft.compiler.schema_structure()'s JSON shape exactly
// (agentdraft explain <schema> --format json, FR-3.5). Keep in sync by hand -
// there is no shared schema generator between the two languages yet.

export type LLMInfo = {
  provider: string;
  model: string;
  system: string | null;
};

export type GraphNode = {
  id: string;
  kind: "llm" | "handler";
  llm: LLMInfo | null;
  handler: string | null;
  tools: string[];
};

export type GraphEdge = {
  from: string;
  kind: "direct" | "conditional";
  to: string | null;
  condition: string | null;
  routes: Record<string, string> | null;
  max_visits: number | null;
  fallback: string | null;
};

export type GraphStructure = {
  schema_version: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export function isGraphStructure(value: unknown): value is GraphStructure {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.schema_version === "number" &&
    Array.isArray(candidate.nodes) &&
    Array.isArray(candidate.edges)
  );
}
