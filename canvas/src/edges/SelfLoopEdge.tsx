import { BaseEdge, EdgeLabelRenderer, type EdgeProps } from "@xyflow/react";

import { buildSelfLoopPath } from "./selfLoopPath";

export function SelfLoopEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  label,
  markerEnd,
  style,
}: EdgeProps) {
  const { path, labelX, labelY } = buildSelfLoopPath(sourceX, sourceY, targetX, targetY);

  return (
    <>
      <BaseEdge id={id} path={path} markerEnd={markerEnd} style={style} />
      {label && (
        <EdgeLabelRenderer>
          <div
            className="self-loop-edge__label"
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              pointerEvents: "all",
            }}
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
