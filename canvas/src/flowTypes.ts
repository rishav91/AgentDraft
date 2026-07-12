import type { Edge, Node } from "@xyflow/react";

export type SchemaNodeData = {
  label: string;
  kind: "llm" | "handler";
  llmSummary: string | null;
  handler: string | null;
  tools: string[];
};

export type EndpointNodeData = {
  label: string;
};

export type SchemaFlowNode = Node<SchemaNodeData, "schemaNode">;
export type EndpointFlowNode = Node<EndpointNodeData, "endpointNode">;
export type AppFlowNode = SchemaFlowNode | EndpointFlowNode;

export type ConditionalEdgeData = {
  condition: string;
};
export type AppFlowEdge = Edge<ConditionalEdgeData>;
