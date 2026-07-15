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
| [ADR-009](#adr-009---checkpointing-backend-langgraph-native-checkpointers) | Checkpointing backend: LangGraph-native checkpointers | Accepted |
| [ADR-010](#adr-010---local-persistence-store-single-shared-sqlite-file-no-db-abstraction) | Local persistence store: single shared SQLite file, no DB abstraction | Accepted |
| [ADR-011](#adr-011---observability-opentelemetry-via-langgraphlangchain-callbacks-no-bundled-backend) | Observability: OpenTelemetry via LangGraph/LangChain callbacks, no bundled backend | Accepted |
| [ADR-012](#adr-012---eval-harness-separate-file-deterministic-assertions-only) | Eval harness: separate file, deterministic assertions only | Accepted |
| [ADR-013](#adr-013---schema-revert-additive-not-destructive) | Schema revert: additive, not destructive | Accepted |
| [ADR-014](#adr-014---resume-schema-consistency-guard) | Resume schema-consistency guard | Accepted |
| [ADR-015](#adr-015---public-distribution-canvas-ui-bundled-into-the-python-wheel) | Public distribution: canvas UI bundled into the Python wheel | Accepted |

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
  porting the referenced Python code - a real cost if/when AgentWeave (Phase 4+) exists.

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
  authors ([PRD §3](PRD.md#3-personas)) makes a standalone app worth the packaging cost. (Revisited:
  [ADR-015](#adr-015---public-distribution-canvas-ui-bundled-into-the-python-wheel)
  answers this without Electron - the prebuilt UI bundled into the Python wheel, not a native shell.)
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

---

## ADR-009 - Checkpointing backend: LangGraph-native checkpointers

**Context.** Phase 1 explicitly excluded memory/persistence/checkpointing (`FR-1.7`, deferred -
see [PRD §2](PRD.md#2-goals--non-goals)). Real usage since then surfaced the need to resume a
crashed or interrupted run rather than re-running an agent from scratch. LangGraph already ships
checkpointer implementations (`MemorySaver`, `SqliteSaver`, `PostgresSaver`) that plug into
`StateGraph.compile(checkpointer=...)` with zero reimplementation required - the same shape of
situation `ADR-005` faced for LLM providers (an existing, multi-backend upstream interface), not
the zero-alternatives situation `ADR-003` ruled out building against.

**Decision.** The schema gains an optional `checkpointer` block (`backend: sqlite` (default) `|
postgres`, plus backend-specific connection info) that the compiler passes to LangGraph's own
checkpointer classes at `StateGraph.compile()` time (`FR-5.1`). `agentdraft run <schema> --resume
<thread_id>` re-invokes the compiled graph against that `thread_id` so LangGraph's own
checkpoint-replay logic resumes execution (`FR-5.3`) - AgentDraft does not implement resume logic
itself. A schema with no `checkpointer` block runs exactly as before (`FR-5.5`) - this is additive,
not a breaking change to existing schemas.

**Alternatives.**
- **Build an AgentDraft-owned checkpoint format, independent of LangGraph.** Rejected: violates
  design tenet 4 ([ARCHITECTURE §1](ARCHITECTURE.md#1-design-tenets)) - compile to the real thing,
  don't reimplement it. LangGraph already solves checkpoint/replay correctly; reimplementing it
  would be pure duplicated risk for no capability gain.
- **SQLite-only, no Postgres option in v1.** Rejected: unlike AgentDraft's own bespoke local
  storage (`ADR-010`), Postgres support already exists in LangGraph for free. Exposing it is a
  one-field passthrough onto an existing upstream interface, the same precedent `ADR-005` set for
  LLM providers - not a new abstraction AgentDraft has to build or maintain.

**Consequences.**
- `+` Zero reimplementation; resumability inherits LangGraph's own tested checkpoint/replay
  semantics rather than a parallel, AgentDraft-specific one.
- `+` Postgres is available to users who want centralized or shared durability, at zero extra
  AgentDraft code beyond a config field and a connection string read from the environment (same
  secrets convention as LLM API keys - never inline in the schema).
- `−` AgentDraft is now coupled to the shape of LangGraph's checkpointer interface, on top of the
  existing `StateGraph` coupling `ADR-003` already accepted. A breaking upstream change to that
  interface has no abstraction layer to absorb it.
- `−` A schema with `checkpointer.backend: postgres` has an external runtime dependency (a
  reachable Postgres instance) that SQLite-backed schemas don't; the local-first default stays
  dependency-free, but this deliberately opens a non-local option.
- `−` Checkpoint resume covers graph *state*, not the real-world side effects of already-executed
  custom-code nodes (e.g. a tool call that already sent an email). AgentDraft does not attempt to
  solve at-least-once/exactly-once semantics for those side effects - the same accepted trust
  boundary the custom-code escape hatch (`ADR-004`) already carries: the author's code, the
  author's responsibility.

---

## ADR-010 - Local persistence store: single shared SQLite file, no DB abstraction

**Context.** Schema version history and run history are AgentDraft-owned data with no upstream
library to lean on - unlike `ADR-009`'s checkpointing, there is no existing multi-backend interface
to pass through. Both need a local store. The idea of a future swappable/pluggable database was
raised, but nothing today needs it - the same shape of premature-abstraction risk `ADR-003` already
named for execution backends.

**Decision.** A single shared SQLite file (`.agentdraft/state.db` by default, alongside the schema
being worked on) holds AgentDraft-owned tables - `schema_versions` (`FR-9.1` schema version history)
and `runs` (`FR-6.1` run ledger) - plus, when `checkpointer.backend: sqlite` (`ADR-009`), LangGraph's
own checkpoint tables in the same physical file (see [DATA-MODEL](DATA-MODEL.md)). No database
abstraction layer, no ORM, no swappable backend for this store - stdlib `sqlite3`, directly. This
extends `ADR-003`'s governing principle to storage: no abstraction is built until a second real
backend need exists for AgentDraft-owned data.

**Alternatives.**
- **Separate SQLite files per feature** (`versions.db`, `runs.db`). Rejected: gives up the free join
  between a run and the checkpoint thread it produced (both keyed by `thread_id` in one file), and
  triples file/migration bookkeeping for no concrete benefit at this scale - local, single user.
- **Build a swappable-DB abstraction now** (e.g. SQLAlchemy or a repository interface), so
  Postgres/MySQL could back this store later too. Rejected: the textbook premature-abstraction trap
  `ADR-003` already ruled out - no second concrete backend need exists for this data today, unlike
  checkpointing, where LangGraph already provides Postgres for free (`ADR-009`).

**Consequences.**
- `+` One file to gitignore, back up, or inspect with any SQLite tool; a run and the checkpoint
  thread it produced live side by side, joinable without a second connection.
- `+` No new dependency (stdlib `sqlite3`), no ORM or migration-framework surface to design or
  maintain.
- `−` If a hosted/multi-user version is ever pursued (already a deferred, not excluded, PRD
  non-goal), this store gets replaced or fronted by something shared - an explicit, accepted future
  cost, the same shape as `ADR-003`'s own accepted cost for the execution backend.
- `−` Concurrent writers (e.g. two `agentdraft run` processes against the same project at once)
  share one SQLite file; SQLite's own locking applies (readers don't block readers, a writer blocks
  other writers briefly). Acceptable for the single local user this store is scoped to; not
  evaluated for concurrent multi-user load.

---

## ADR-011 - Observability: OpenTelemetry spans around compiled node functions, no bundled backend

**Context.** Production use of a compiled agent needs visibility into per-node latency, token
usage, and failures across a run - today, the only way to see any of this is stdout during `run`
or a post-hoc read of the run ledger (`FR-6.1`). The [README](README.md) previously deferred an
Observability doc entirely ("no tracing UI until a canvas exists to host it"); that reasoning no
longer applies once real emission is being built, independent of any UI.

**Decision.** Emit OpenTelemetry spans - one root span per run, one child span per node (`FR-7.1`),
token usage as span attributes where the underlying LangChain response exposes it (`FR-7.2`) - by
wrapping each compiled node's function at compile time, the same extension point `compiler.py`
already uses to wrap a node for visit-tracking (`FR-1.12`). Export is OTLP-based, driven entirely
by standard OpenTelemetry environment variables (`OTEL_EXPORTER_OTLP_ENDPOINT` etc., `FR-7.3`) - no
AgentDraft-specific config surface. AgentDraft ships no bundled trace-storage/UI backend (`FR-7.4`);
[OBSERVABILITY.md](OBSERVABILITY.md) documents self-hosted options (Langfuse, SigNoz, HyperDX,
Arize Phoenix) users may point OTLP at.

**Alternatives.**
- **Hook in via LangGraph/LangChain's `BaseCallbackHandler` system**, the original plan for this
  ADR. Rejected during implementation: a compiled graph's callback events include many internal
  sub-runs tagged `langsmith:hidden` with no `name` and only a `metadata['langgraph_node']` key to
  identify the real node - reliably filtering these down to "one clean span per node" means
  depending on an undocumented, version-coupled internal convention. Wrapping the node function
  AgentDraft already owns gets an equally real span, with real start/end times and direct access to
  the node's own return value for token-usage extraction, none of that fragility.
- **Build a bespoke AgentDraft-specific tracing format and local viewer.** Rejected: duplicates
  what OpenTelemetry already standardizes, locks users into an AgentDraft-only tool, and is a much
  larger build than emitting standard OTel spans.
- **Bundle a specific backend** (e.g. ship a Langfuse integration as the default/only path).
  Rejected: picks a vendor/opinion for every user regardless of their existing stack - the same
  category of premature commitment `ADR-003` avoids for execution backends, applied here to
  telemetry sinks.

**Consequences.**
- `+` Vendor-neutral: any OTLP-compatible backend works with zero AgentDraft code changes, today or
  in the future.
- `+` No new always-on infrastructure for users who don't set the OTLP env var - `opentelemetry-api`'s
  own default (no provider ever installed) creates non-recording spans, verified directly: zero
  network calls, no export machinery touched (`NFR-8.1`).
- `+` Node-level spans only cover schema-defined nodes (`llm`/`handler`), not the synthesized
  `{node}__tools` tool-execution nodes the compiler adds internally - a deliberate scope match to
  what a schema author thinks of as "a node" (`FR-3.5`'s `schema_structure`), not every LangGraph
  implementation detail.
- `−` AgentDraft takes a new direct (non-optional) dependency on `opentelemetry-sdk` and an OTLP/HTTP
  exporter purely for instrumentation, even though it bundles no backend to send data to by default.
- `−` No default local visualization out of the box - someone who wants to see a trace today must
  stand up, or point at an existing, OTel-compatible backend themselves. A deliberate cost of
  staying vendor-neutral, not an oversight.
- `−` OTel's global tracer provider can be installed at most once per process (an OTel SDK
  restriction, not an AgentDraft choice) - harmless for a real `agentdraft run` invocation (one
  process per run), but means the "endpoint configured -> provider installed" code path is
  exercised by manual/smoke testing rather than the automated suite, to avoid one test's exporter
  configuration leaking into every later test in the same pytest process.

---

## ADR-012 - Eval harness: separate file, deterministic assertions only

**Context.** A schema or prompt edit can silently regress agent behavior with no automated way to
catch it before the next `agentdraft run`. An eval/regression harness needs a home for test cases
and a decision on what kinds of assertions it supports.

**Decision.** Eval cases live in a separate YAML file, not embedded in the schema, referencing a
schema by path (`FR-8.1`); `agentdraft eval <schema> <evals-file>` compiles the schema once and
runs every case, asserting against final graph state using deterministic checks only - field
equality, substring, regex - via a dotted/indexed path into the final state (`FR-8.2`, `FR-8.3`).
A new exit code `4` (eval assertion failure) is appended to the CLI's exit-code taxonomy
([ARCHITECTURE §4.4](ARCHITECTURE.md#44-exit-codes)), distinct from `1`/`2`/`3` since the schema
compiled and ran without error - the failure is in the agent's *behavior*, not AgentDraft's
handling of it (`FR-8.4`).

**Alternatives.**
- **Embed an `evals:` section in the schema file itself.** Rejected: mixes graph structure with
  test fixtures in one file, and complicates `ADR-006`'s `schema_version` semantics - is adding a
  test case a schema-format change?
- **Support LLM-as-judge assertions for free-form output in v1.** Rejected: a regression safety net
  should itself be non-flaky and free to run repeatedly in CI; LLM-as-judge assertions introduce
  cost, latency, and non-determinism into the tool meant to catch regressions, and would need the
  AI-architecture-level treatment (prompt-injection surface, an explicit "earns its place" case)
  this project doesn't yet need elsewhere. Revisit if deterministic assertions prove insufficient
  for real agents whose primary output is prose.

**Consequences.**
- `+` Eval runs are reproducible and free to run on every commit, the same posture as the existing
  CI approach (`NFR-6.4`).
- `+` Schema files stay focused on structure; an evals file is disposable/editable independently -
  the same relationship the canvas's JSON export already has to the schema (`ADR-007`).
- `−` Cannot assert on the *quality* or semantic correctness of free-form LLM output, only on
  structural/deterministic aspects of final state - a real coverage gap for agents whose main
  output is prose, accepted for now (`ADR-012` alternatives).
- `−` A new exit code changes a documented stable contract (`CLAUDE.md`); existing scripts checking
  `if exit_code != 0` are unaffected, but anything branching specifically on `3` vs. "everything
  else" needs updating for the new `4` case - called out explicitly here since exit codes are
  conventionally not changed casually.

---

## ADR-013 - Schema revert: additive, not destructive

**Context.** `ADR-010` established a single, linear, append-only `schema_versions` table - one row
per distinct content change, revision numbers never reused. Adding a "go back to an older version"
command (`FR-9.5`) raises the same question git's `revert` vs. `reset` split answers differently:
does going back rewrite/discard history, or add to it?

**Decision.** `agentdraft schema revert <schema> <rev>` restores the working file to `rev`'s
recorded content and records that as a **new** revision via the existing `record_revision`
(git-`revert` semantics), rather than deleting or renumbering anything after `rev` (git-`reset`
semantics). `record_revision`'s existing dedup-by-hash behavior already makes a no-op revert (target
content equals the current tip) safe - no duplicate row.

**Alternatives.**
- **Rewind: delete/discard every revision after `rev`, making it the new tip.** Rejected: destructive
  with no undo (this is a local-only tool with no separate backup of `schema_versions`), and it
  makes "revert to a revision that itself only existed because of a later edit" - i.e. jumping back
  *forward* in time after a revert - impossible without re-deriving that content by hand. The
  append-only alternative solves this for free: revision numbers are permanent, so any revision is
  revertable-to at any point, indefinitely.
- **A HEAD-pointer/branching model (full git semantics).** Rejected outright per the project's
  governing principle - no abstraction (here, branch/merge complexity) until a concrete need exists;
  a single local user editing one schema file has no use for concurrent history lines.

**Consequences.**
- `+` Nothing is ever destroyed; "I reverted and now want the version from before I reverted" is
  just another `schema revert` call, not a special case.
- `+` No new error class or edge case beyond the existing `RevisionNotFoundError` (`ADR`-level reuse
  of `FR-9.3`'s diff-lookup machinery).
- `−` The `schema_versions` table only ever grows - acceptable at this project's scale (single user,
  hand-authored schemas), same trade-off already accepted for the run ledger and version history in
  general (`ADR-010`); pruning isn't offered for this table, unlike `runs` (`FR-6.4`).

---

## ADR-014 - Resume schema-consistency guard

**Context.** `agentdraft run --resume <thread_id>` (`ADR-009`) compiles whatever schema is currently
on disk and resumes LangGraph's checkpoint replay against it. If the schema changed - hand-edited, or
restored via `schema revert` (`ADR-013`) - between the original run and the resume, this silently
resumes against a *different compiled graph* than the one that produced the checkpoint: renamed or
removed nodes, changed prompts, different tool bindings. `runs.py` already records a
`schema_content_hash` per run (`FR-6.1`) but nothing had ever read it back on resume - a real gap in
the durability guarantee Phase 3 exists to provide (`NFR-7.1`).

**Decision.** On `--resume`, look up the most recent recorded run for that `thread_id`
(`get_latest_run_for_thread`) and compare its `schema_content_hash` against the current schema
file's hash. A mismatch fails fast (exit `1`) before any execution, naming the problem explicitly;
a new `--force` flag bypasses the check for a user who deliberately wants to resume against a
changed schema. When no prior run is recorded for that `thread_id` (e.g. the run ledger was pruned,
`FR-6.4`, or the checkpoint didn't originate from `agentdraft run`), there is no baseline to compare
against, so the guard is skipped rather than blocking (`FR-5.6`).

**Alternatives.**
- **Warn but proceed on mismatch, instead of failing.** Rejected: a warning is easy to miss in
  scripted/CI usage, and the failure mode being guarded against (silently diverging agent behavior)
  is exactly the kind of thing `NFR-2.1`'s "fail loud and specific" posture exists to prevent -
  consistent with the existing "no checkpoint found for thread_id" error already failing hard rather
  than starting a fresh, silently-different run.
- **Store and check the full schema content (or the target compiled-graph structure), not just a
  hash.** Rejected: the hash is already computed and recorded for `FR-6.1`'s own purposes; comparing
  hashes is sufficient to detect "same bytes or not" and needs no new storage or comparison logic.
- **Block unconditionally, no `--force` override.** Rejected: some schema edits between runs are
  genuinely benign (e.g. a comment-only change, or an intentional forward-compatible prompt tweak)
  and a user who has verified that should be able to proceed without editing the schema back first.

**Consequences.**
- `+` Closes a real correctness gap: resuming a crashed run can no longer silently execute a
  different graph than the one that produced its checkpoint.
- `+` No new storage: reuses the `schema_content_hash` `FR-6.1` already records and a straightforward
  new lookup (`get_latest_run_for_thread`) on the existing `runs` table.
- `−` The guard is only as good as the run ledger: pruning a thread's runs (`FR-6.4`) removes the
  baseline it needs, silently re-opening the gap this ADR closes for that thread. Documented as a
  known limitation rather than solved, since a fully robust version would need a way to protect a
  thread's runs from pruning while its checkpoint is still resumable - not built until that proves
  to be a real problem, per the project's governing principle.

---

## ADR-015 - Public distribution: canvas UI bundled into the Python wheel

**Context.** AgentDraft has never been published anywhere - `pyproject.toml` had no PyPI-facing
metadata, `canvas/package.json` is `private: true`, and `agentdraft canvas <schema>` only starts
the local editing API and tells the user to separately `cd canvas && npm run dev` from a cloned
repo. A real `pip install`-only consumer has no `canvas/` source tree to `cd` into. ADR-007 flagged
this exact gap as a future decision ("revisit if/when ... distribution to other authors makes a
standalone app worth the packaging cost") without resolving it. This ADR resolves it, now that
Phase 3 (production hardening) is done and public distribution is the next phase (Phase 3.5,
[ROADMAP](ROADMAP.md)).

An earlier version of this ADR chose to publish the canvas as its own independently-versioned npm
package (`agentdraft-canvas`), consumed via `npx agentdraft-canvas --api-base <url>` alongside
`agentdraft canvas`. That was reconsidered before implementation shipped: comparable local-first
dev tools with a companion web UI - Streamlit, Jupyter Lab, MLflow, Prefect, Arize Phoenix, Gradio -
all bundle their prebuilt frontend into the Python package instead, so one `pip install` gives a
working UI with no separate Node.js install for the end user. Nothing embeds AgentDraft's canvas
outside of AgentDraft itself today, so there is no real second consumer of it as a standalone JS
package - exactly the situation this project's own governing principle says not to build
speculative decoupling for.

**Decision.**
- **The canvas frontend's prebuilt static assets ship inside the `agent-draft` Python wheel** -
  no separate npm package, no second install command. A new Hatchling build hook
  (`hatch_build.py`) runs `npm ci && npm run build` in `canvas/` at wheel-build time (skipped if
  `canvas/dist` already exists, or if `npm` isn't on `PATH` - a Python-only contributor without
  Node still gets a working package, just without a bundled UI) and copies the output into
  `src/agentdraft/canvas_static/`, which `pyproject.toml`'s `artifacts` config force-includes in
  the wheel (it's generated, not tracked in git). Only whoever builds/publishes the wheel needs
  Node.js - never the end user installing it from PyPI.
- **`agentdraft canvas <schema>` now serves both the JSON API and this bundled UI from one
  process, one port.** `server.py` extends its existing `/api/*`-prefixed routing with a static
  file handler for everything else, falling back to `index.html` for any unmatched path (no
  client-side routing today, but a direct load of any path should still work), and refusing to
  serve outside `canvas_static/` (path traversal).
- **The canvas's API base becomes runtime-configurable**, not just Vite's build-time
  `VITE_API_BASE`. The bundled static build is served on a different port every run (whatever the
  OS assigns), so the API base can't be baked in at `npm run build` time - it has to come from the
  server that's actually serving it. `server.py` serves a synthetic `GET /agentdraft-config.js`
  route that injects `window.__AGENTDRAFT_API_BASE__ = ""` (empty string = "same origin as this
  server"); `canvas/src/apiBase.ts` resolves `VITE_API_BASE` (still used by canvas contributors
  running `npm run dev` against a separately-running `agentdraft canvas` instance, unaffected by
  any of this) with a fallback to that runtime value - checking `!== undefined` rather than
  truthiness, since an empty string is a real, meaningful "configured" value here, not an absence
  of one.

**Alternatives.**
- **Publish the canvas as its own npm package** (`agentdraft-canvas`, consumed via `npx
  agentdraft-canvas --api-base <url>`). The initial decision, reconsidered as above - it keeps
  release cadences fully independent, but at the cost of a second required install command and
  Node.js as a hard dependency for anyone who wants the UI at all, for no offsetting benefit given
  there's no real second consumer of the canvas as a standalone package today. Revisit if that
  changes (e.g. someone wants to embed the canvas's React Flow view in another app).
- **Rewrite `index.html`'s `<script>` tag with the API base baked in at serve time**, instead of a
  separate `/agentdraft-config.js` route. Rejected: mutating built HTML is fragile to Vite's build
  output format changing across versions; serving one additional static-looking JS file is a
  stable, mechanical contract that doesn't depend on `dist/index.html`'s exact shape.

**Consequences.**
- `+` Resolves ADR-007's open question with a concrete, implemented answer instead of a deferred
  "revisit later."
- `+` `pip install agent-draft` followed by `agentdraft canvas <schema>` gives a fully working UI
  with zero Node.js involvement for the end user - the actual blocker this ADR sets out to fix,
  and the simplest possible consumer-facing story (one install, one command, one URL).
- `+` The Python package and the canvas UI can never drift out of sync with each other (they ship
  in the same artifact), unlike the independent-packages alternative.
- `−` The canvas UI's release cadence is now coupled to the Python package's - a canvas-only fix
  requires a full backend patch release to reach end users. Accepted given there's no concrete
  need for independent cadences today.
- `−` Building a real (non-dev) wheel now requires Node.js/npm on whatever machine or CI runner
  does the build - `publish-python.yml` needs `actions/setup-node` alongside `actions/setup-python`.
  A plain `pip install -e ".[dev]"` for Python-only contributors still works without Node (the hook
  degrades gracefully), and CI's main test job sets `AGENTDRAFT_SKIP_CANVAS_BUILD=1` to stay fast
  and deterministic regardless of what's on the runner.
