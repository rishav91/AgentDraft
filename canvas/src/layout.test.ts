import { describe, expect, it } from "vitest";

import { layoutGraph } from "./layout";
import type { GraphStructure } from "./types";

const SIMPLE: GraphStructure = {
  schema_version: 1,
  nodes: [
    {
      id: "chat",
      kind: "llm",
      llm: { provider: "anthropic", model: "claude-sonnet-5", system: null },
      handler: null,
      tools: [],
    },
  ],
  edges: [
    { from: "START", kind: "direct", to: "chat", condition: null, routes: null },
    { from: "chat", kind: "direct", to: "END", condition: null, routes: null },
  ],
};

const COMPREHENSIVE: GraphStructure = {
  schema_version: 1,
  nodes: [
    {
      id: "router",
      kind: "llm",
      llm: { provider: "anthropic", model: "claude-sonnet-5", system: null },
      handler: null,
      tools: [],
    },
    {
      id: "search",
      kind: "llm",
      llm: { provider: "anthropic", model: "claude-sonnet-5", system: null },
      handler: null,
      tools: ["tests.support.tools:echo"],
    },
    { id: "shout", kind: "handler", llm: null, handler: "tests.support.handlers:uppercase", tools: [] },
  ],
  edges: [
    { from: "START", kind: "direct", to: "router", condition: null, routes: null },
    {
      from: "router",
      kind: "conditional",
      to: null,
      condition: "tests.support.routing:by_last_message_content",
      routes: { positive: "search", negative: "shout" },
    },
    { from: "search", kind: "direct", to: "shout", condition: null, routes: null },
    { from: "shout", kind: "direct", to: "END", condition: null, routes: null },
  ],
};

describe("layoutGraph", () => {
  it("synthesizes START/END endpoint nodes alongside schema nodes", () => {
    const { nodes } = layoutGraph(SIMPLE);

    const schemaNodes = nodes.filter((n) => n.type === "schemaNode");
    const endpointNodes = nodes.filter((n) => n.type === "endpointNode");
    expect(schemaNodes).toHaveLength(1);
    expect(endpointNodes).toHaveLength(2);
    expect(endpointNodes.map((n) => n.id).sort()).toEqual(["END", "START"]);
  });

  it("maps llm node fields into SchemaNodeData", () => {
    const { nodes } = layoutGraph(SIMPLE);

    const chat = nodes.find((n) => n.id === "chat");
    expect(chat?.data).toMatchObject({
      label: "chat",
      kind: "llm",
      llmSummary: "anthropic/claude-sonnet-5",
      handler: null,
      tools: [],
    });
  });

  it("maps handler node fields into SchemaNodeData", () => {
    const { nodes } = layoutGraph(COMPREHENSIVE);

    const shout = nodes.find((n) => n.id === "shout");
    expect(shout?.data).toMatchObject({
      label: "shout",
      kind: "handler",
      llmSummary: null,
      handler: "tests.support.handlers:uppercase",
    });
  });

  it("produces one direct edge per direct GraphStructure edge", () => {
    const { edges } = layoutGraph(SIMPLE);

    expect(edges).toHaveLength(2);
    expect(edges.every((e) => e.type === "smoothstep")).toBe(true);
    expect(edges.map((e) => [e.source, e.target])).toEqual([
      ["START", "chat"],
      ["chat", "END"],
    ]);
  });

  it("expands a conditional edge's routes into one labeled, dashed edge per route", () => {
    const { edges } = layoutGraph(COMPREHENSIVE);

    const conditionalEdges = edges.filter((e) => e.source === "router");
    expect(conditionalEdges).toHaveLength(2);
    expect(conditionalEdges.map((e) => e.label).sort()).toEqual(["negative", "positive"]);
    expect(conditionalEdges.map((e) => e.target).sort()).toEqual(["search", "shout"]);
    for (const edge of conditionalEdges) {
      expect(edge.style?.strokeDasharray).toBe("5 5");
      expect(edge.data?.condition).toBe("tests.support.routing:by_last_message_content");
    }
  });

  it("assigns unique ids to every edge, including expanded conditional routes", () => {
    const { edges } = layoutGraph(COMPREHENSIVE);

    const ids = edges.map((e) => e.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
