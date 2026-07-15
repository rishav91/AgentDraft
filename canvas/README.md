# AgentDraft Canvas

Visualization and editing of a compiled AgentDraft schema (Phase 2.1/2.2 — see
[../docs/ROADMAP.md](../docs/ROADMAP.md), [../docs/ADRs.md](../docs/ADRs.md) ADR-007/ADR-008).

React + TypeScript + Vite app. Its prebuilt static assets ship bundled inside the `agent-draft`
Python wheel (`ADR-015`) - most users never touch this directory at all, they just run
`agentdraft canvas <schema.yaml>` (see the root [README](../README.md)). This directory is for
building that bundle and for contributors working on the UI itself.

It has three modes, selected by whether an API base is configured (via `VITE_API_BASE` at build
time, or `window.__AGENTDRAFT_API_BASE__` at runtime, injected by `agentdraft canvas`'s own
server, `ADR-015`) - no code changes needed to switch between them.

## Bundled mode (what `agentdraft canvas` actually runs, Phase 3.5)

Nothing to do here - `pip install agent-draft` already contains a prebuilt copy of this app.
`agentdraft canvas <schema.yaml>` serves it directly, on the same port as the editing API:

```sh
agentdraft canvas schema.yaml   # open the URL it prints - that's it
```

`server.py` serves this directory's prebuilt `dist/` plus a synthetic `GET /agentdraft-config.js`
route that sets `window.__AGENTDRAFT_API_BASE__ = ""` (same origin as the server itself) -
`src/apiBase.ts` resolves that with a fallback from `VITE_API_BASE`, so this mode and the
dev-server mode below share the same app code with no divergence.

## View-only mode (no backend, Phase 2.1)

```sh
npm install
npm run dev
```

From the main repo, export a schema's compiled structure:

```sh
agentdraft explain <schema.yaml> --format json > graph.json
```

Open the running app and load `graph.json` via the file picker or drag-and-drop. No interface to
the Python compiler beyond that one file — no backend process, no live connection.

## Editing mode (local API server, from source, Phase 2.2)

For contributors iterating on the UI itself, with fast HMR against a real running API instead of a
rebuild-and-reload cycle. From the main repo, start the local editing API for a schema:

```sh
agentdraft canvas <schema.yaml>
```

By default, handler/condition/tool suggestions (FR-4.5) are discovered by scanning the whole
current directory (excluding AgentDraft's own package, `.venv`, `node_modules`, etc.). To restrict
suggestions to specific directories - e.g. leaving a project's `tests/` out - repeat `--scan-dir`:

```sh
agentdraft canvas <schema.yaml> --scan-dir handlers --scan-dir tools
```

It prints the API's URL (e.g. `http://127.0.0.1:54321`). Point the canvas dev server at it:

```sh
VITE_API_BASE=http://127.0.0.1:54321 npm run dev
```

The app auto-loads the graph from the API instead of showing the file picker, and becomes
editable: add/remove nodes, edit LLM config (provider/model/system/tools) or a handler reference,
and edit a node's outgoing routing (direct targets, or a single condition+routes block — the same
XOR shape `Schema`'s `Edge` model enforces). **Save** POSTs the edited graph back; it's parsed
through the same `Schema` pydantic model the CLI uses (`ADR-008`), so an invalid edit is rejected
with the same field-specific errors `agentdraft validate` would give, and the file on disk is left
untouched until a save succeeds.

## What it renders

Everything `agentdraft explain` prints: node ids, `llm` (provider/model) vs `handler`
(custom-code reference), bound tools, and edges — direct or conditional (labeled by route key,
dashed). No divergence from the text `explain` output is the Phase 2.1 exit criterion.

JS test coverage and CI are covered by the `canvas:` job in `.github/workflows/ci.yml` (lint,
typecheck+build, Vitest, Playwright e2e) - shipped as Phase 2.3.
