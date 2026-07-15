---
name: canvas-dev
description: Start the Agentic Graph Composer canvas app against a real schema in live editing mode, or in view-only mode from an exported graph. Use when asked to run/preview the canvas, test a canvas change against real data, or debug the canvas <-> API server integration.
---

Canvas has two modes, selected purely by whether `VITE_API_BASE` is set - no code changes needed.

## Editing mode (preferred for testing changes - live, editable, backed by a real schema)

1. From the repo root, start the local editing API server for a schema file:
   ```sh
   agc canvas <schema.yaml>
   ```
   It prints the API's URL, e.g. `http://127.0.0.1:54321` (port is OS-assigned, changes each run).
   By default it scans the whole current directory for handler/condition/tool suggestions; pass
   `--scan-dir <dir>` (repeatable) to restrict discovery if that's slow or noisy.
2. In a second terminal, from `canvas/`, point the dev server at that API:
   ```sh
   VITE_API_BASE=http://127.0.0.1:54321 npm run dev
   ```
3. Open the printed Vite URL. The app auto-loads the graph from the API (no file picker) and is
   editable - add/remove nodes, edit LLM/handler config, edit routing. **Save** POSTs the edit back
   through the same pydantic `Schema` model the CLI uses, so invalid edits are rejected with the
   same errors `agc validate` would give, and the file on disk is untouched until save
   succeeds.

There's no example schema checked in for quick testing - use `examples/docs_qa.yaml` (note: this one
needs a real `ANTHROPIC_API_KEY` env var to actually *run* the agent, but not just to load/edit it in
canvas) or any fixture under `tests/fixtures/`.

## View-only mode (no backend process, just a static export)

1. From the repo root, export a schema's compiled structure:
   ```sh
   agc explain <schema.yaml> --format json > graph.json
   ```
2. From `canvas/`, run `npm run dev` with no `VITE_API_BASE` set, and load `graph.json` via the file
   picker or drag-and-drop in the running app.

Use this mode when there's no need to save edits, or when just checking that `agc explain`'s
output renders correctly (the text `explain` output and the canvas rendering must never diverge -
that's the Phase 2.1 exit criterion).
