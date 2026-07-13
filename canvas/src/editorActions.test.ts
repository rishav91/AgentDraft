import { describe, expect, it } from "vitest";

import {
  addDirectTarget,
  addNode,
  clearOutgoing,
  nextNodeId,
  outgoingEdges,
  removeNode,
  setOutgoingConditional,
  setOutgoingDirect,
  updateNode,
} from "./editorActions";
import type { GraphStructure } from "./types";

function schema(): GraphStructure {
  return {
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
        tools: [],
      },
      { id: "shout", kind: "handler", llm: null, handler: "pkg:fn", tools: [] },
    ],
    edges: [
      { from: "START", kind: "direct", to: "router", condition: null, routes: null },
      {
        from: "router",
        kind: "conditional",
        to: null,
        condition: "pkg:route",
        routes: { positive: "search", negative: "shout" },
      },
      { from: "search", kind: "direct", to: "shout", condition: null, routes: null },
      { from: "shout", kind: "direct", to: "END", condition: null, routes: null },
    ],
  };
}

describe("nextNodeId", () => {
  it("picks the lowest unused node_N id, skipping reserved and taken ones", () => {
    expect(nextNodeId(schema())).toBe("node_4");
  });
});

describe("addNode", () => {
  it("appends a new llm node with a generated id and no outgoing edges", () => {
    const next = addNode(schema());

    const added = next.nodes.at(-1)!;
    expect(added.kind).toBe("llm");
    expect(outgoingEdges(next, added.id)).toEqual([]);
  });
});

describe("updateNode", () => {
  it("patches fields on the target node only", () => {
    const next = updateNode(schema(), "search", { llm: { provider: "openai", model: "gpt-5", system: null } });

    expect(next.nodes.find((n) => n.id === "search")?.llm?.provider).toBe("openai");
    expect(next.nodes.find((n) => n.id === "router")).toEqual(schema().nodes[0]);
  });

  it("cascades an id rename to every edge referencing the old id", () => {
    const next = updateNode(schema(), "search", { id: "researcher" });

    expect(next.nodes.some((n) => n.id === "search")).toBe(false);
    expect(next.edges.find((e) => e.from === "search")).toBeUndefined();
    expect(next.edges.find((e) => e.from === "researcher")).toBeDefined();
    const conditional = next.edges.find((e) => e.kind === "conditional");
    expect(conditional?.routes).toEqual({ positive: "researcher", negative: "shout" });
  });
});

describe("removeNode", () => {
  it("produces no cleanup note when nothing else references the removed node", () => {
    const withOrphan: GraphStructure = {
      ...schema(),
      nodes: [
        ...schema().nodes,
        {
          id: "orphan",
          kind: "llm",
          llm: { provider: "anthropic", model: "claude-sonnet-5", system: null },
          handler: null,
          tools: [],
        },
      ],
      edges: [...schema().edges, { from: "orphan", kind: "direct", to: "END", condition: null, routes: null }],
    };

    const { structure, cleanups } = removeNode(withOrphan, "orphan");

    expect(structure.nodes.some((n) => n.id === "orphan")).toBe(false);
    expect(structure.edges.some((e) => e.from === "orphan")).toBe(false);
    expect(cleanups).toEqual([]);
  });

  it("drops a direct edge that targeted the removed node, with a cleanup note", () => {
    const { structure, cleanups } = removeNode(schema(), "shout");

    expect(structure.edges.some((e) => e.kind === "direct" && e.to === "shout")).toBe(false);
    expect(cleanups.some((c) => c.includes("search"))).toBe(true);
  });

  it("strips a matching route from a conditional edge, keeping the rest", () => {
    const { structure, cleanups } = removeNode(schema(), "search");

    const conditional = structure.edges.find((e) => e.kind === "conditional");
    expect(conditional?.routes).toEqual({ negative: "shout" });
    expect(cleanups.some((c) => c.includes("route"))).toBe(true);
  });

  it("drops a conditional edge entirely once its last route is removed", () => {
    const withOneRoute = setOutgoingConditional(schema(), "router", "pkg:route", {
      positive: "search",
    });

    const { structure, cleanups } = removeNode(withOneRoute, "search");

    expect(structure.edges.some((e) => e.from === "router")).toBe(false);
    expect(cleanups.some((c) => c.includes("no routes left"))).toBe(true);
  });
});

describe("setOutgoingDirect / setOutgoingConditional / clearOutgoing", () => {
  it("replaces a conditional edge with one direct edge per target", () => {
    const next = setOutgoingDirect(schema(), "router", ["search", "shout"]);

    const edges = outgoingEdges(next, "router");
    expect(edges).toHaveLength(2);
    expect(edges.every((e) => e.kind === "direct")).toBe(true);
    expect(edges.map((e) => e.to).sort()).toEqual(["search", "shout"]);
  });

  it("replaces direct edges with a single conditional edge", () => {
    const next = setOutgoingConditional(schema(), "search", "pkg:cond", { ok: "shout" });

    const edges = outgoingEdges(next, "search");
    expect(edges).toHaveLength(1);
    expect(edges[0].kind).toBe("conditional");
    expect(edges[0].routes).toEqual({ ok: "shout" });
  });

  it("clearOutgoing removes all of a node's outgoing edges", () => {
    const next = clearOutgoing(schema(), "router");

    expect(outgoingEdges(next, "router")).toEqual([]);
  });
});

describe("addDirectTarget", () => {
  it("appends a new direct target for a node with only direct edges", () => {
    const next = addDirectTarget(schema(), "search", "router");

    expect(outgoingEdges(next, "search").map((e) => e.to).sort()).toEqual(["router", "shout"]);
  });

  it("is a no-op if the source node is already conditional", () => {
    const next = addDirectTarget(schema(), "router", "shout");

    expect(next).toEqual(schema());
  });

  it("is a no-op if the target is already wired", () => {
    const next = addDirectTarget(schema(), "search", "shout");

    expect(outgoingEdges(next, "search")).toEqual(outgoingEdges(schema(), "search"));
  });
});
