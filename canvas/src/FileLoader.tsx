import { useCallback, useState, type DragEvent } from "react";

import { isGraphStructure, type GraphStructure } from "./types";

type FileLoaderProps = {
  onLoad: (structure: GraphStructure) => void;
};

export function FileLoader({ onLoad }: FileLoaderProps) {
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);

  const handleFile = useCallback(
    async (file: File) => {
      setError(null);
      try {
        const text = await file.text();
        const parsed: unknown = JSON.parse(text);
        if (!isGraphStructure(parsed)) {
          setError("That file doesn't look like an `agc explain --format json` export.");
          return;
        }
        onLoad(parsed);
      } catch (err) {
        setError(err instanceof Error ? `Couldn't parse JSON: ${err.message}` : "Couldn't parse JSON.");
      }
    },
    [onLoad],
  );

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragActive(false);
    const file = event.dataTransfer.files[0];
    if (file) void handleFile(file);
  };

  return (
    <div
      className={`file-loader ${dragActive ? "file-loader--active" : ""}`}
      onDragOver={(event) => {
        event.preventDefault();
        setDragActive(true);
      }}
      onDragLeave={() => setDragActive(false)}
      onDrop={onDrop}
    >
      <h1>Agentic Graph Composer Canvas</h1>
      <p>
        Load a graph exported with <code>agc explain &lt;schema&gt; --format json</code>.
      </p>
      <label className="file-loader__button">
        Choose file
        <input
          type="file"
          accept="application/json"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void handleFile(file);
          }}
        />
      </label>
      <p className="file-loader__hint">or drag and drop the JSON file here</p>
      {error && <p className="file-loader__error">{error}</p>}
    </div>
  );
}
