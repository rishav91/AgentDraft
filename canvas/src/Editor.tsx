import { useCallback, useEffect, useState } from "react";

import type { Connection } from "@xyflow/react";

import { fetchCallables, fetchProviders, fetchSchemas, openSchema, saveGraph } from "./api";
import type { SchemaEntry } from "./api";
import {
  addDirectTarget,
  addNode,
  removeNode,
  setOutgoingConditional,
  setOutgoingDirect,
  updateNode,
} from "./editorActions";
import { GraphCanvas } from "./GraphCanvas";
import { Inspector } from "./Inspector";
import { SchemaSidebar } from "./SchemaSidebar";
import type { GraphNode, GraphStructure } from "./types";

type EditorProps = {
  apiBase: string;
  initialStructure: GraphStructure;
};

export function Editor({ apiBase, initialStructure }: EditorProps) {
  const [structure, setStructure] = useState(initialStructure);
  const [dirty, setDirty] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [saveErrors, setSaveErrors] = useState<string[] | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [callables, setCallables] = useState<string[]>([]);
  const [providers, setProviders] = useState<string[]>([]);
  const [schemas, setSchemas] = useState<SchemaEntry[]>([]);
  const [activePath, setActivePath] = useState<string | null>(null);

  const refreshSchemas = useCallback(() => {
    fetchSchemas(apiBase).then(({ active, schemas: list }) => {
      setSchemas(list);
      setActivePath(active);
    });
  }, [apiBase]);

  useEffect(() => {
    fetchCallables(apiBase).then(setCallables);
    fetchProviders(apiBase).then(setProviders);
    refreshSchemas();
  }, [apiBase, refreshSchemas]);

  const mutate = (next: GraphStructure) => {
    setStructure(next);
    setDirty(true);
    setSaveErrors(null);
  };

  const handleAddNode = () => {
    const next = addNode(structure);
    mutate(next);
    setSelectedNodeId(next.nodes[next.nodes.length - 1].id);
  };

  const handleRemoveNode = () => {
    if (!selectedNodeId) return;
    const { structure: next, cleanups } = removeNode(structure, selectedNodeId);
    mutate(next);
    setSelectedNodeId(null);
    setNotice(cleanups.length > 0 ? `Also cleaned up: ${cleanups.join("; ")}` : null);
  };

  const handleUpdateNode = (patch: Partial<GraphNode>) => {
    if (!selectedNodeId) return;
    const next = updateNode(structure, selectedNodeId, patch);
    mutate(next);
    if (patch.id) setSelectedNodeId(patch.id);
  };

  const handleConnect = (connection: Connection) => {
    if (!connection.source || !connection.target) return;
    mutate(addDirectTarget(structure, connection.source, connection.target));
  };

  const handleSetOutgoingDirect = (targets: string[]) => {
    if (!selectedNodeId) return;
    mutate(setOutgoingDirect(structure, selectedNodeId, targets));
  };

  const handleSetOutgoingConditional = (
    condition: string,
    routes: Record<string, string>,
    maxVisits: number | null,
    fallback: string | null,
  ) => {
    if (!selectedNodeId) return;
    mutate(
      setOutgoingConditional(structure, selectedNodeId, condition, routes, maxVisits, fallback),
    );
  };

  const handleSave = async () => {
    setSaving(true);
    setNotice(null);
    const result = await saveGraph(apiBase, structure);
    setSaving(false);
    if (result.ok) {
      setDirty(false);
      setSaveErrors(null);
      setNotice("Saved.");
      refreshSchemas();
    } else {
      setSaveErrors(result.errors);
    }
  };

  const handleSwitchSchema = async (path: string) => {
    setNotice(null);
    setSaveErrors(null);
    const result = await openSchema(apiBase, path);
    if (result.ok) {
      setStructure(result.structure);
      setDirty(false);
      setSelectedNodeId(null);
      setActivePath(path);
      refreshSchemas();
    } else {
      setSaveErrors(result.errors);
    }
  };

  return (
    <div className="editor">
      <div className="editor__toolbar">
        {activePath && <span className="editor__active-path">{activePath}</span>}
        <span>schema_version: {structure.schema_version}</span>
        <button type="button" onClick={handleAddNode}>
          + Add node
        </button>
        <button type="button" onClick={() => void handleSave()} disabled={!dirty || saving}>
          {saving ? "Saving..." : "Save"}
        </button>
        {dirty && <span className="editor__dirty">unsaved changes</span>}
      </div>
      {notice && <div className="editor__notice">{notice}</div>}
      {saveErrors && (
        <div className="editor__errors">
          {saveErrors.map((err, i) => (
            <p key={i}>{err}</p>
          ))}
        </div>
      )}
      <div className="editor__body">
        <SchemaSidebar
          schemas={schemas}
          activePath={activePath}
          disabled={dirty}
          onSelect={(path) => void handleSwitchSchema(path)}
        />
        <div className="editor__canvas">
          <GraphCanvas
            structure={structure}
            mode="edit"
            selectedNodeId={selectedNodeId}
            onConnect={handleConnect}
            onNodeClick={setSelectedNodeId}
          />
        </div>
        {selectedNodeId && (
          <Inspector
            key={selectedNodeId}
            structure={structure}
            nodeId={selectedNodeId}
            apiBase={apiBase}
            callables={callables}
            providers={providers}
            onUpdateNode={handleUpdateNode}
            onRemoveNode={handleRemoveNode}
            onSetOutgoingDirect={handleSetOutgoingDirect}
            onSetOutgoingConditional={handleSetOutgoingConditional}
          />
        )}
      </div>
    </div>
  );
}
