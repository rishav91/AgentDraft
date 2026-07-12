# AgentDraft Canvas

Read-only visualization of a compiled AgentDraft schema (Phase 2.1 — see
[../docs/ROADMAP.md](../docs/ROADMAP.md), [../docs/ADRs.md](../docs/ADRs.md) ADR-007).

Standalone React + TypeScript + Vite app, separate from the Python package. It has no interface
to the Python compiler beyond a JSON file you export by hand — no backend process, no live
connection.

## Run it

```sh
npm install
npm run dev
```

From the main repo, export a schema's compiled structure:

```sh
agentdraft explain <schema.yaml> --format json > graph.json
```

Then open the running app and load `graph.json` via the file picker or drag-and-drop.

## What it renders

Exactly what `agentdraft explain` prints as text, laid out visually with React Flow: node ids,
`llm` (provider/model) vs `handler` (custom-code reference), bound tools, and edges — direct or
conditional (labeled by route key, dashed). No divergence from the text `explain` output is the
Phase 2.1 exit criterion.

Not yet supported (later sub-phases): editing a graph and writing changes back to the schema
(2.2), and JS test coverage / CI (2.3).
