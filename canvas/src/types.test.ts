import { describe, expect, it } from "vitest";

import { isGraphStructure } from "./types";

describe("isGraphStructure", () => {
  it("accepts a well-shaped structure", () => {
    expect(isGraphStructure({ schema_version: 1, nodes: [], edges: [] })).toBe(true);
  });

  it.each([
    ["not an object", null],
    ["a bare array", []],
    ["a string", "not json"],
    ["missing schema_version", { nodes: [], edges: [] }],
    ["schema_version as a string", { schema_version: "1", nodes: [], edges: [] }],
    ["nodes not an array", { schema_version: 1, nodes: {}, edges: [] }],
    ["edges not an array", { schema_version: 1, nodes: [], edges: {} }],
  ])("rejects %s", (_label, value) => {
    expect(isGraphStructure(value)).toBe(false);
  });
});
