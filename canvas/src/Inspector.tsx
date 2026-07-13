import { useState } from "react";

import { CallableField } from "./CallableField";
import { outgoingEdges } from "./editorActions";
import type { GraphNode, GraphStructure } from "./types";

type InspectorProps = {
  structure: GraphStructure;
  nodeId: string;
  apiBase: string;
  callables: string[];
  onUpdateNode: (patch: Partial<GraphNode>) => void;
  onRemoveNode: () => void;
  onSetOutgoingDirect: (targets: string[]) => void;
  onSetOutgoingConditional: (condition: string, routes: Record<string, string>) => void;
};

const RESERVED_IDS = new Set(["START", "END"]);
const CALLABLES_DATALIST_ID = "agentdraft-callables";

export function Inspector({
  structure,
  nodeId,
  apiBase,
  callables,
  onUpdateNode,
  onRemoveNode,
  onSetOutgoingDirect,
  onSetOutgoingConditional,
}: InspectorProps) {
  const node = structure.nodes.find((n) => n.id === nodeId);
  const [idDraft, setIdDraft] = useState(nodeId);
  const [idError, setIdError] = useState<string | null>(null);

  if (!node) return null;

  const otherIds = structure.nodes.filter((n) => n.id !== nodeId).map((n) => n.id);
  const targetOptions = [...otherIds, "END"];

  const commitId = () => {
    if (idDraft === nodeId) return;
    if (!idDraft.trim()) {
      setIdError("id can't be empty");
      return;
    }
    if (RESERVED_IDS.has(idDraft) || otherIds.includes(idDraft)) {
      setIdError(`'${idDraft}' is already in use`);
      return;
    }
    setIdError(null);
    onUpdateNode({ id: idDraft });
  };

  const edges = outgoingEdges(structure, nodeId);
  const isConditional = edges.some((edge) => edge.kind === "conditional");
  const directTargets = isConditional
    ? []
    : edges.map((edge) => edge.to).filter((to): to is string => to !== null);
  const conditionalEdge = edges.find((edge) => edge.kind === "conditional");
  const condition = conditionalEdge?.condition ?? "";
  const routes = conditionalEdge?.routes ?? {};

  return (
    <aside className="inspector">
      <datalist id={CALLABLES_DATALIST_ID}>
        {callables.map((c) => (
          <option key={c} value={c} />
        ))}
      </datalist>

      <div className="inspector__field">
        <label>id</label>
        <input
          value={idDraft}
          onChange={(e) => setIdDraft(e.target.value)}
          onBlur={commitId}
        />
        {idError && <p className="inspector__error">{idError}</p>}
      </div>

      <div className="inspector__field">
        <label>kind</label>
        <div className="inspector__radio-row">
          <label>
            <input
              type="radio"
              checked={node.kind === "llm"}
              onChange={() =>
                onUpdateNode({
                  kind: "llm",
                  llm: node.llm ?? { provider: "", model: "", system: null },
                  handler: null,
                })
              }
            />
            llm
          </label>
          <label>
            <input
              type="radio"
              checked={node.kind === "handler"}
              onChange={() =>
                onUpdateNode({ kind: "handler", llm: null, handler: node.handler ?? "", tools: [] })
              }
            />
            handler
          </label>
        </div>
      </div>

      {node.kind === "llm" ? (
        <>
          <div className="inspector__field">
            <label>provider</label>
            <input
              value={node.llm?.provider ?? ""}
              onChange={(e) =>
                onUpdateNode({ llm: { ...(node.llm ?? { model: "", system: null }), provider: e.target.value } })
              }
            />
          </div>
          <div className="inspector__field">
            <label>model</label>
            <input
              value={node.llm?.model ?? ""}
              onChange={(e) =>
                onUpdateNode({ llm: { ...(node.llm ?? { provider: "", system: null }), model: e.target.value } })
              }
            />
          </div>
          <div className="inspector__field">
            <label>system</label>
            <textarea
              value={node.llm?.system ?? ""}
              onChange={(e) =>
                onUpdateNode({
                  llm: {
                    ...(node.llm ?? { provider: "", model: "" }),
                    system: e.target.value || null,
                  },
                })
              }
            />
          </div>
          <div className="inspector__field">
            <label>tools</label>
            {node.tools.map((tool, i) => (
              <div className="inspector__row" key={i}>
                <CallableField
                  value={tool}
                  apiBase={apiBase}
                  callables={callables}
                  datalistId={CALLABLES_DATALIST_ID}
                  onChange={(value) => {
                    const tools = [...node.tools];
                    tools[i] = value;
                    onUpdateNode({ tools });
                  }}
                />
                <button
                  type="button"
                  onClick={() => onUpdateNode({ tools: node.tools.filter((_, j) => j !== i) })}
                >
                  &times;
                </button>
              </div>
            ))}
            <button type="button" onClick={() => onUpdateNode({ tools: [...node.tools, ""] })}>
              + add tool
            </button>
          </div>
        </>
      ) : (
        <div className="inspector__field">
          <label>handler</label>
          <CallableField
            value={node.handler ?? ""}
            apiBase={apiBase}
            callables={callables}
            datalistId={CALLABLES_DATALIST_ID}
            placeholder="module.path:function_name"
            onChange={(value) => onUpdateNode({ handler: value })}
          />
        </div>
      )}

      <div className="inspector__field">
        <label>outgoing routing</label>
        <div className="inspector__radio-row">
          <label>
            <input
              type="radio"
              checked={!isConditional}
              onChange={() => onSetOutgoingDirect(directTargets)}
            />
            direct
          </label>
          <label>
            <input
              type="radio"
              checked={isConditional}
              onChange={() => onSetOutgoingConditional(condition, routes)}
            />
            conditional
          </label>
        </div>

        {!isConditional ? (
          <>
            {directTargets.map((target, i) => (
              <div className="inspector__row" key={i}>
                <select
                  value={target}
                  onChange={(e) => {
                    const updated = [...directTargets];
                    updated[i] = e.target.value;
                    onSetOutgoingDirect(updated);
                  }}
                >
                  {targetOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() =>
                    onSetOutgoingDirect(directTargets.filter((_, j) => j !== i))
                  }
                >
                  &times;
                </button>
              </div>
            ))}
            <button
              type="button"
              disabled={targetOptions.length === 0}
              onClick={() => onSetOutgoingDirect([...directTargets, targetOptions[0]])}
            >
              + add direct edge
            </button>
          </>
        ) : (
          <>
            <CallableField
              value={condition}
              apiBase={apiBase}
              callables={callables}
              datalistId={CALLABLES_DATALIST_ID}
              placeholder="module.path:function_name"
              onChange={(value) => onSetOutgoingConditional(value, routes)}
            />
            {Object.entries(routes).map(([key, target], i) => (
              <div className="inspector__row" key={i}>
                <input
                  value={key}
                  placeholder="route key"
                  onChange={(e) => {
                    const updated = Object.fromEntries(
                      Object.entries(routes).map(([k, v]) => [k === key ? e.target.value : k, v]),
                    );
                    onSetOutgoingConditional(condition, updated);
                  }}
                />
                <select
                  value={target}
                  onChange={(e) =>
                    onSetOutgoingConditional(condition, { ...routes, [key]: e.target.value })
                  }
                >
                  {targetOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => {
                    const { [key]: _omit, ...rest } = routes;
                    onSetOutgoingConditional(condition, rest);
                  }}
                >
                  &times;
                </button>
              </div>
            ))}
            <button
              type="button"
              disabled={targetOptions.length === 0}
              onClick={() =>
                onSetOutgoingConditional(condition, {
                  ...routes,
                  [`route_${Object.keys(routes).length + 1}`]: targetOptions[0],
                })
              }
            >
              + add route
            </button>
          </>
        )}
      </div>

      <button type="button" className="inspector__delete" onClick={onRemoveNode}>
        Delete node
      </button>
    </aside>
  );
}
