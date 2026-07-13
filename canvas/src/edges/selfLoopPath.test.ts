import { describe, expect, it } from "vitest";

import { NODE_HEIGHT } from "../layout";
import { buildSelfLoopPath } from "./selfLoopPath";

describe("buildSelfLoopPath", () => {
  it("starts exactly at the source handle and ends exactly at the target handle", () => {
    const { path } = buildSelfLoopPath(220, 36, 0, 36);

    expect(path.startsWith("M 220 36")).toBe(true);
    expect(path.endsWith("0 36")).toBe(true);
  });

  it("clears the node's actual top edge, not just an offset from the handle center", () => {
    // sourceY/targetY are the node's vertical CENTER (Position.Right/Left),
    // so the real top edge is NODE_HEIGHT/2 above them - the whole point of
    // this fix (unlike the earlier Bezier attempt) is exact clearance from
    // that real edge, not an arbitrary pixel guess.
    const sourceY = 36;
    const { labelY } = buildSelfLoopPath(220, sourceY, 0, sourceY);

    const nodeTopY = sourceY - NODE_HEIGHT / 2;
    expect(labelY).toBeLessThan(nodeTopY);
  });

  it("is a closed set of connected segments (no gaps) from source to target", () => {
    const { path } = buildSelfLoopPath(220, 36, 0, 36);

    // every coordinate pair after the initial M should chain from the
    // previous point - spot check the path only uses L/Q commands after M
    const commands = path.match(/[A-Z]/g);
    expect(commands?.[0]).toBe("M");
    expect(commands?.slice(1).every((c) => c === "L" || c === "Q")).toBe(true);
  });

  it("centers the label horizontally between the two stubs, not the raw handles", () => {
    const { labelX } = buildSelfLoopPath(220, 36, 0, 36);

    // stubs are symmetric (same offset on each side), so the midpoint is
    // still the midpoint of the raw handles
    expect(labelX).toBe(110);
  });
});
