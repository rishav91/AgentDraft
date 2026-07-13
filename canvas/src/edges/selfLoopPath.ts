import { NODE_HEIGHT } from "../layout";

const CLEARANCE_ABOVE_NODE = 20;
const STUB = 24;
const CORNER_RADIUS = 8;

// React Flow's built-in edge types (smoothstep, bezier, step) all assume a
// source and target on different nodes - when both resolve to the same
// node's handles (a self-loop, e.g. FR-1.12's `revise: draft` on `draft`
// itself), their path math degenerates to nothing visible.
//
// A smooth Bezier arc was tried first and rejected: a cubic Bezier's
// vertical rise near its endpoints is inherently gradual (only ~48% of its
// total height by 20% of the way along), so a fixed pixel offset isn't
// enough clearance and the curve visibly cuts through the node's corners.
// An orthogonal step path (up, across, down - matching the right-angle
// style the rest of the canvas already uses for conditional edges) gives
// exact, guaranteed clearance instead of an approximation: up to a height
// computed from the node's real top edge (sourceY/targetY are the node's
// vertical center, per `Position.Right`/`Position.Left`), not a guess.
export function buildSelfLoopPath(
  sourceX: number,
  sourceY: number,
  targetX: number,
  targetY: number,
): { path: string; labelX: number; labelY: number } {
  const nodeTopY = Math.min(sourceY, targetY) - NODE_HEIGHT / 2;
  const loopY = nodeTopY - CLEARANCE_ABOVE_NODE;
  const rightX = sourceX + STUB;
  const leftX = targetX - STUB;

  const path = [
    `M ${sourceX} ${sourceY}`,
    `L ${rightX - CORNER_RADIUS} ${sourceY}`,
    `Q ${rightX} ${sourceY} ${rightX} ${sourceY - CORNER_RADIUS}`,
    `L ${rightX} ${loopY + CORNER_RADIUS}`,
    `Q ${rightX} ${loopY} ${rightX - CORNER_RADIUS} ${loopY}`,
    `L ${leftX + CORNER_RADIUS} ${loopY}`,
    `Q ${leftX} ${loopY} ${leftX} ${loopY + CORNER_RADIUS}`,
    `L ${leftX} ${targetY - CORNER_RADIUS}`,
    `Q ${leftX} ${targetY} ${leftX - CORNER_RADIUS} ${targetY}`,
    `L ${targetX} ${targetY}`,
  ].join(" ");

  return { path, labelX: (rightX + leftX) / 2, labelY: loopY };
}
