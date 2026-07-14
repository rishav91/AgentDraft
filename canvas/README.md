# AgentDraft Canvas

Visualization and editing of a compiled AgentDraft schema (Phase 2.1/2.2 — see
[../docs/ROADMAP.md](../docs/ROADMAP.md), [../docs/ADRs.md](../docs/ADRs.md) ADR-007/ADR-008).

Standalone React + TypeScript + Vite app, separate from the Python package. It has three modes,
selected by whether an API base is configured (via `VITE_API_BASE` at build time, or
`window.__AGENTDRAFT_API_BASE__` at runtime, `ADR-015`) - no code changes needed to switch between
them.

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

## npm consumer mode (published package, Phase 3.5, `ADR-015`)

No repo clone needed. Start the editing API from the Python package, then point the published
`agentdraft-canvas` package at it:

```sh
agentdraft canvas <schema.yaml>                       # prints its URL, e.g. http://127.0.0.1:54321
npx agentdraft-canvas --api-base http://127.0.0.1:54321
```

`agentdraft-canvas` ships a prebuilt static bundle plus a thin Node server (`canvas/bin/agentdraft-canvas.js`)
that serves it and injects the `--api-base` value at runtime via a `/agentdraft-config.js` route -
this is why it doesn't need `VITE_API_BASE` (a Vite *build-time* env var, unusable for a single
published bundle shared by every consumer). `src/App.tsx` resolves
`import.meta.env.VITE_API_BASE ?? window.__AGENTDRAFT_API_BASE__`, so this mode and the dev-server
mode below share the same app code with no divergence.

## Editing mode (local API server, from source, Phase 2.2)

From the main repo, start the local editing API for a schema:

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
