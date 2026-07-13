# AgentDraft Canvas

Visualization and editing of a compiled AgentDraft schema (Phase 2.1/2.2 — see
[../docs/ROADMAP.md](../docs/ROADMAP.md), [../docs/ADRs.md](../docs/ADRs.md) ADR-007/ADR-008).

Standalone React + TypeScript + Vite app, separate from the Python package. It has two modes,
selected by whether `VITE_API_BASE` is set — no code changes needed to switch between them.

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

## Editing mode (local API server, Phase 2.2)

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

Not yet covered: JS test coverage / CI (2.3, in progress).
