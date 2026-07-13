# Architecture Decision Records — AgentDraft

See [README](README.md) for the doc map. Each ADR: context → decision → alternatives → consequences.
Referenced by ID (`ADR-00N`) from other docs.

## Index

| ID | Title | Status |
|---|---|---|
| [ADR-001](#adr-001--schema-format-yaml) | Schema format: YAML | Accepted |
| [ADR-002](#adr-002--implementation-language-python) | Implementation language: Python | Accepted |
| [ADR-003](#adr-003--no-backend-abstraction-in-v1) | No backend abstraction in v1 | Accepted |
| [ADR-004](#adr-004--custom-code-escape-hatch) | Custom-code escape hatch for undeclarable logic | Accepted |
| [ADR-005](#adr-005--llm-provider-agnostic-config) | LLM provider-agnostic config | Accepted |
| [ADR-006](#adr-006--schema-versioning) | Schema versioning | Accepted |
| [ADR-007](#adr-007--canvas-frontend-stack-and-data-interface) | Canvas frontend stack and data interface | Accepted |
| [ADR-008](#adr-008--canvas-write-back-a-local-api-server) | Canvas write-back: a local API server | Accepted |

---

## ADR-001 — Schema format: YAML

**Context.** Agents need to be defined declaratively (`FR-1`). The format must be hand-authorable —
Phase 1's primary interaction mode is a human editing schema files directly, before any canvas exists.

**Decision.** Use YAML as the schema file format.

**Alternatives.**
- **JSON.** No ambiguity, trivial to map to/from the canvas's future in-memory representation.
  Rejected for v1 because it has no comments and more punctuation noise, both of which hurt
  hand-authoring — the primary Phase 1 workflow.
- **A custom DSL.** Could be more terse/expressive than generic YAML. Rejected: requires building
  and maintaining a parser/grammar plus editor tooling (syntax highlighting, LSP) from scratch,
  a cost disproportionate to Phase 1's scope.

**Consequences.**
- `+` Comments and lower punctuation density make hand-authoring easier.
- `+` Familiar format (same family as k8s manifests, GitHub Actions, etc.) — low learning cost.
- `−` YAML's indentation sensitivity and type-coercion quirks (e.g. `yes`/`no` as booleans) are a
  known source of subtle authoring bugs; the schema parser (`FR-1.2`) must produce clear errors
  rather than passing YAML's own cryptic ones through.
- `−` Less convenient than JSON if/when the canvas (Phase 2) needs to serialize its in-memory graph
  back to a schema file — an extra YAML-formatting step versus a direct JSON dump.

---

## ADR-002 — Implementation language: Python

**Context.** The compiler must target LangGraph's `StateGraph` API. LangGraph has both a Python and
a JavaScript (`langgraph.js`) implementation.

**Decision.** Build the compiler and CLI in Python.

**Alternatives.**
- **TypeScript/Node.** Would let a future canvas (likely a web/Electron UI) share code and types
  with the compiler. Rejected for Phase 1: `langgraph.js` has historically lagged the Python
  implementation in features, and targeting it would mean building against a less mature surface.

**Consequences.**
- `+` Compiles directly against LangGraph's most mature, most feature-complete implementation.
- `+` No FFI or subprocess boundary between AgentDraft and LangGraph.
- `−` If the canvas (Phase 2) is a web/Electron frontend, it will need its own language (likely
  TypeScript) and a defined interface to the Python compiler/CLI (e.g. shelling out, or a local
  API) — a boundary this decision defers rather than avoids.

---

## ADR-003 — No backend abstraction in v1

**Context.** The original project idea proposed an execution-backend interface so LangGraph could
be swapped for AgentWeave (a planned custom SDK) later. AgentWeave does not exist yet, and its
justification is learning/control over agent execution internals rather than a concrete gap in
LangGraph today (see [PRD](PRD.md)).

**Decision.** AgentDraft's compiler, CLI (Phase 1), and canvas (Phase 2) call LangGraph directly.
No execution-backend interface, no capability-negotiation layer, no backend-neutral skills/MCP
abstraction is built until AgentWeave exists as a second, real, concrete consumer.

**Alternatives.**
- **Design the backend interface now, alongside Phase 1.** Rejected: with only one implementation
  (LangGraph) to design against, the interface's shape would be guessed rather than derived from
  real variance between two backends. This is the textbook premature-abstraction trap — the
  interface would likely need reworking once AgentWeave is real anyway, so building it early buys
  nothing and costs Phase 1 velocity.
- **Design a minimal/speculative interface just for future-proofing.** Rejected for the same
  reason — "minimal" abstractions designed against zero real alternatives still encode guesses
  about what needs to vary.

**Consequences.**
- `+` Phase 1 ships faster — no interface design/maintenance overhead.
- `+` The eventual backend interface (if AgentWeave is built) will be derived from two real
  implementations, not guessed in advance.
- `−` If/when AgentWeave is built, extracting the interface will require refactoring the compiler
  and CLI's LangGraph-specific call sites — an explicit, accepted future cost.
- `−` AgentDraft is, for the entire Phase 1-2 horizon, hard-coupled to LangGraph. A LangGraph
  breaking change has no abstraction layer to absorb it (see [ARCHITECTURE §7](ARCHITECTURE.md#7-failure-modes--degradation)).

---

## ADR-004 — Custom-code escape hatch

**Context.** LangGraph nodes and conditional edges can run arbitrary Python. A purely declarative
schema cannot express arbitrary logic without becoming a general-purpose programming language
itself. The project's named failure condition (`PRD §7`) is the schema needing constant escape
hatches for real agents — but the opposite failure, a schema with *no* escape hatch, means any
agent needing non-trivial logic can't be expressed at all.

**Decision.** The schema supports a typed "custom code" node/edge that references a user-supplied
Python callable by import path (e.g. `handler: myagent.nodes:custom_router`), resolved at compile
time by the custom-code loader (`FR-1.6`, [ARCHITECTURE §3](ARCHITECTURE.md#3-components)).

**Alternatives.**
- **No escape hatches — the schema must express everything, or it's a schema-language bug.**
  Rejected: this blocks Phase 1 on covering LangGraph's full flexibility before shipping anything,
  and conflicts with "deep before wide" (tenet 3) — Phase 1 deliberately covers one agent shape,
  not all of LangGraph's expressiveness.
- **Embed a scripting/expression language in the schema (e.g. Jinja-style expressions for routing
  logic).** Rejected: adds a second language surface to design, document, and debug, for
  functionality Python (the escape hatch) already covers.

**Consequences.**
- `+` No agent is ever fully blocked by schema coverage gaps.
- `+` Matches how LangGraph itself works — nodes are just functions — so the escape hatch isn't a
  foreign concept bolted on top.
- `−` Escape-hatch usage is exactly the failure signal the project is watching (`PRD §6` —
  "near-zero escape-hatch usage" is the expressiveness success metric). High usage means the
  schema isn't actually capturing real agent shapes, and the escape hatch could mask that by
  making failure quiet instead of loud.
- `−` A schema with escape-hatch nodes is not fully portable to a different backend without also
  porting the referenced Python code — a real cost if/when AgentWeave (Phase 3+) exists.

---

## ADR-005 — LLM provider-agnostic config

**Context.** LangGraph nodes consume a LangChain chat model object. LangChain already provides a
common interface across providers (Anthropic, OpenAI, Google, and others) via `init_chat_model(model,
model_provider=...)` — a provider-agnostic abstraction with many real, existing consumers, unlike the
execution-backend question in `ADR-003` where only one backend (LangGraph) exists today. The schema's
LLM node config (`FR-1.3`) needs to decide whether to hardcode one vendor or expose provider choice.

**Decision.** The schema's LLM node config includes explicit `provider` and `model` fields, mapped
directly onto LangChain's existing provider registry. AgentDraft does not build its own provider
abstraction.

**Alternatives.**
- **Hardcode a single provider for Phase 1** (e.g. Anthropic only). Rejected: locks users into one
  vendor from day one and is more costly to retrofit later than to expose the provider field now,
  given LangChain already provides multi-provider support for free.
- **Build AgentDraft's own provider abstraction/registry.** Rejected: this is the opposite mistake
  from `ADR-003` — LangChain's provider interface already has multiple real, battle-tested
  consumers, so building a second one duplicates effort and drifts from upstream as new providers
  are added there.

**Consequences.**
- `+` Users pick a provider per node with zero AgentDraft-authored provider-specific code.
- `+` New providers LangChain adds upstream work automatically, no AgentDraft changes needed.
- `−` The schema's LLM config is coupled to the shape of LangChain's provider interface (provider
  name strings, parameter names); if that shape changes upstream, the schema's LLM config section
  may need to change too.
- `−` Not every provider name LangChain accepts is necessarily well-supported or stable; schema
  validation (`FR-1.3`) must give a clear, field-specific error for an unrecognized or misspelled
  provider name rather than surfacing a deep LangChain stack trace (`NFR-2.1`).

---

## ADR-006 — Schema versioning

**Context.** The schema format will change over time — Phase 1's P2-deferred items alone (memory
config `FR-1.7`, sandboxing `FR-1.8`, multi-agent composition `FR-1.9`) will add new fields and
possibly change existing ones. Without a version marker, there is no way to distinguish "old schema,
new parser" from "malformed schema" — both look like the same class of error.

**Decision.** Every schema file includes a required `schema_version` field, identifying which version
of the AgentDraft schema format it targets (`FR-1.10`). Phase 1 ships as `schema_version: 1`.

**Alternatives.**
- **No version field; treat the schema format as always-current.** Rejected: cheap now, but any
  future breaking schema change becomes a silent failure or a confusing generic error for anyone
  with an older file — exactly the failure mode `NFR-2.1` (field-specific errors) exists to avoid.
  Retrofitting a version field after schema files already exist in the wild is strictly harder than
  adding it before any exist.
- **Semver-style version string (e.g. `"1.2.0"`) instead of a single integer.** Rejected for Phase 1:
  no minor/patch schema evolution is anticipated yet, and a bare integer is simpler to validate and
  reason about. Revisit if the schema format needs finer-grained compatibility signaling later.

**Consequences.**
- `+` A version mismatch produces a specific, actionable error ("this file targets schema version
  N, this AgentDraft build supports version M") instead of a generic parse failure.
- `+` Establishes the hook future migration tooling would need, without building that tooling now —
  consistent with the governing principle (`README`): the version field itself has an immediate
  consumer (clear-error validation, `FR-1.10`), migration tooling does not yet and isn't built.
- `−` One more required field in every schema file, including trivial ones — a small, permanent
  authoring cost accepted in exchange for avoiding silent breakage later.

---

## ADR-007 — Canvas frontend stack and data interface

**Context.** Phase 2 (canvas) requires rendering (2.1) and, later, editing (2.2) a compiled
schema's structure. `ADR-002` flagged but deferred this exact boundary: "if the canvas is a
web/Electron frontend, it will need its own language (likely TypeScript) and a defined interface
to the Python compiler/CLI (e.g. shelling out, or a local API)." [ROADMAP](ROADMAP.md) left the
canvas's framework and test-tooling explicitly "TBD when Phase 2 scope is planned." This ADR
resolves that deferred boundary now that Phase 2 planning has started, scoped to what sub-phase
2.1 (read-only rendering) needs.

**Decision.**
- **Frontend:** a local web app, not Electron, built with React + TypeScript + Vite.
- **Data interface:** a static JSON export of the compiled graph structure — no running backend
  process. `agentdraft explain <schema> --format json` (`FR-3.5`) is the canvas's sole data
  source; the canvas loads a JSON file client-side (browser File API), with no HTTP API and no
  live process talking to the Python compiler.
- **Graph rendering:** React Flow (`@xyflow/react`) for node/edge rendering, pan/zoom, and layout
  primitives, with `dagre` for automatic layout (the schema itself carries no position data).

**Alternatives.**
- **Electron.** Rejected for 2.1: a native desktop shell adds packaging/build/auto-update
  machinery disproportionate to a single-user, read-only viewer — nothing about read-only
  rendering needs OS-level integration. Revisit if/when 2.2 (editing) or distribution to other
  authors ([PRD §3](PRD.md#3-personas)) makes a standalone app worth the packaging cost.
- **A local HTTP API serving compiled-graph JSON on demand.** Rejected for 2.1: introduces a
  long-running backend process (lifecycle, port management, CORS) for a sub-phase whose only
  requirement is rendering an already-compiled, static structure. A static export is the literal
  shape of the 2.1 exit criterion ([ROADMAP](ROADMAP.md)) — "no divergence between what `explain`
  prints and what the canvas shows" is satisfied by the same data feeding two renderers, with no
  live channel between them to keep in sync. Revisit for 2.2, which needs a write path back to
  the schema file and may justify a local server then.
- **Custom SVG/Canvas rendering instead of React Flow.** Rejected: reimplements pan/zoom/layout
  that React Flow already provides, for no concrete benefit at this stage; React Flow has a clear
  upgrade path to 2.2 editing (drag, connect, select) for free.

**Consequences.**
- `+` Zero new backend process/lifecycle to build or reason about for 2.1 — the CLI already
  produces the JSON (`FR-3.5`), the canvas already just reads a file.
- `+` `schema_structure()` (the Python function backing both `explain`'s text output and
  `--format json`) is the single source of truth for graph structure, so the "no divergence"
  exit criterion holds by construction, not by discipline.
- `+` React Flow gives 2.2 (editing) a natural extension point — the same node/edge model, now
  mutable — instead of a rewrite.
- `−` No live connection between the running compiler and the canvas: editing (2.2) will need its
  own interface decision (e.g. writing schema YAML back to disk, possibly via a local server then)
  — explicitly deferred, not solved here.
- `−` Two runtimes (Python and Node/TypeScript) now exist in the repo, each with its own
  dependency and build tooling — the anticipated cost `ADR-002` accepted in advance.

---

## ADR-008 — Canvas write-back: a local API server

**Context.** `ADR-007` deferred exactly this question: 2.1's static-JSON, no-backend-process
model works for read-only viewing, but 2.2 (editing) needs a way for canvas changes to reach the
schema file on disk. `Schema`'s validation rules (`schema.py`) are non-trivial and will keep
growing (memory config `FR-1.7`, sandboxing `FR-1.8`, multi-agent composition `FR-1.9` are all
still coming per [PRD](PRD.md)) — whatever write-back mechanism is chosen either reuses those
rules or re-implements a second copy of them.

**Decision.** `agentdraft canvas <schema>` starts a small local HTTP server (Python stdlib
`http.server.ThreadingHTTPServer`, no new dependency), bound to `127.0.0.1` only, no
authentication (`NFR-4.2`). It exposes `GET /api/graph` (current `schema_structure`, reloaded
from disk each call) and `POST /api/save` (`FR-4.3`): the request body is parsed via
`schema_from_structure` directly into the same `Node`/`Edge`/`Schema` pydantic models
`load_schema` uses, so every existing validation rule applies for free with zero duplicated
logic; a valid save is written via `save_schema` (`FR-1.11`), an invalid one returns HTTP 422
with the same field-specific error text the CLI prints (`format_validation_errors`, `FR-4.4`,
`NFR-2.1`). The server only runs for the duration of an editing session — 2.1's plain viewing
still needs nothing running (`ADR-007` unchanged for that path).

**Alternatives.**
- **Browser File System Access API.** Rejected: keeps `ADR-007`'s "no server" invariant fully
  intact, but means re-implementing `Schema`'s validation and YAML round-tripping in TypeScript —
  a second copy of rules that will drift from `schema.py` as the schema format grows. Also
  Chromium-only, a portability constraint the local-server option doesn't have.
- **Manual export/download, hand-overwrite the file.** Rejected: simplest to build, but barely
  qualifies as "write the changes back to the schema" (ROADMAP 2.2's own wording) and is a rough,
  easy-to-fumble UX for a tool whose pitch is making iteration faster, not slower.

**Consequences.**
- `+` Zero duplicated validation logic — the local server is a thin transport wrapper around
  functions the CLI already has (`schema_from_structure`, `save_schema`, `format_validation_errors`).
- `+` Canvas-reported save errors are guaranteed to match CLI-reported ones for the same invalid
  input, since both paths run through the same pydantic models.
- `−` Reintroduces a running backend process, but scoped to editing sessions only — a narrower
  reversal of `ADR-007` than making 2.1's viewing mode depend on a server too.
- `−` No authentication (`NFR-4.2`): any local process can read and overwrite the schema file
  while the server runs. Accepted under the same trust boundary the custom-code escape hatch
  already established (`NFR-4.1`) — local-only, single-user, the schema author already has full
  local code execution regardless.
