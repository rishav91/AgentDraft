import { Handle, Position, type NodeProps } from "@xyflow/react";

import type { SchemaFlowNode } from "../flowTypes";

export function SchemaNode({ data }: NodeProps<SchemaFlowNode>) {
  return (
    <div className={`schema-node schema-node--${data.kind}`}>
      <Handle type="target" position={Position.Left} />
      <div className="schema-node__title">{data.label}</div>
      {data.kind === "llm" ? (
        <div className="schema-node__badge">llm: {data.llmSummary}</div>
      ) : (
        <div className="schema-node__badge">handler: {data.handler}</div>
      )}
      {data.tools.length > 0 && (
        <div className="schema-node__tools">
          {data.tools.map((tool) => (
            <span key={tool} className="schema-node__tool-chip" title={tool}>
              {tool.split(":").pop()}
            </span>
          ))}
        </div>
      )}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
