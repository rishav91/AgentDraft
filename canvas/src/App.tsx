import { useEffect, useState } from "react";

import { fetchGraph } from "./api";
import { resolveApiBase } from "./apiBase";
import { Editor } from "./Editor";
import { FileLoader } from "./FileLoader";
import { GraphCanvas } from "./GraphCanvas";
import type { GraphStructure } from "./types";

const API_BASE = resolveApiBase();

export function App() {
  // "" (same origin, ADR-015) counts as configured - only a genuinely unset
  // API_BASE means no backend at all (view-only mode).
  return API_BASE !== undefined ? <ApiApp apiBase={API_BASE} /> : <ViewOnlyApp />;
}

// Unchanged from Phase 2.1: no API configured -> static file picker, read-only canvas.
function ViewOnlyApp() {
  const [structure, setStructure] = useState<GraphStructure | null>(null);

  if (!structure) {
    return <FileLoader onLoad={setStructure} />;
  }

  return (
    <div className="app">
      <header className="app__header">
        <span>schema_version: {structure.schema_version}</span>
        <button type="button" onClick={() => setStructure(null)}>
          Load a different file
        </button>
      </header>
      <div className="app__canvas">
        <GraphCanvas structure={structure} />
      </div>
    </div>
  );
}

// Phase 2.2: an API is configured -> auto-load and hand off to the editor.
function ApiApp({ apiBase }: { apiBase: string }) {
  const [structure, setStructure] = useState<GraphStructure | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchGraph(apiBase)
      .then(setStructure)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)));
  }, [apiBase]);

  if (error) {
    return (
      <div className="file-loader">
        <h1>AgentDraft Canvas</h1>
        <p className="file-loader__error">
          Couldn't load from {apiBase}: {error}
        </p>
      </div>
    );
  }

  if (!structure) {
    return (
      <div className="file-loader">
        <h1>AgentDraft Canvas</h1>
        <p>Loading from {apiBase}...</p>
      </div>
    );
  }

  return <Editor apiBase={apiBase} initialStructure={structure} />;
}
