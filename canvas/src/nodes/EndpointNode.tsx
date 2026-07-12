import { Handle, Position, type NodeProps } from "@xyflow/react";

import type { EndpointFlowNode } from "../flowTypes";

export function EndpointNode({ data }: NodeProps<EndpointFlowNode>) {
  return (
    <div className="endpoint-node">
      <Handle type="target" position={Position.Left} />
      {data.label}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
