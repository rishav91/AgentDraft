import { useState } from "react";

import { FileLoader } from "./FileLoader";
import { GraphCanvas } from "./GraphCanvas";
import type { GraphStructure } from "./types";

export function App() {
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
