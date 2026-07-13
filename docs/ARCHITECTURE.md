# Architecture — AgentDraft

See [README](README.md) for the doc map. See [PRD](PRD.md) for why this exists.

## 1. Design tenets

1. **No abstraction before a second real consumer.** AgentDraft compiles and runs directly against
   LangGraph. No execution-backend interface, no capability-negotiation layer, until AgentWeave
   exists and forces the seam (`ADR-003`).
2. **The schema is the source of truth for structure; code is the source of truth for logic that
   can't be declared.** A schema describes nodes, edges, and config. A typed custom-code node
   references a plain Python callable when logic genuinely can't be expressed declaratively (`ADR-004`).
3. **Deep before wide.** Phase 1 covers one agent shape (single-agent, tool-calling) thoroughly
   rather than covering many shapes shallowly. Memory, sandboxing, and multi-agent composition are
   deferred, not half-built.
4. **Compile to the real thing, not a re-implementation.** The compiler's output is a genuine
   LangGraph `StateGraph`. AgentDraft does not reimplement graph execution, tool calling, or LLM
   invocation — it only translates schema into LangGraph's own primitives.

## 2. High-level architecture (Phase 1)

```mermaid
flowchart LR
    A[YAML schema file] --> B[Parser / validator]
    B --> C[Compiler]
    C --> D[LangGraph StateGraph]
    D --> E[Execution]
    E --> F[CLI output]

    G[agentdraft validate] --> B
    H[agentdraft run] --> B
    I[agentdraft explain] --> C
```

Everything left of `LangGraph StateGraph` is AgentDraft. Everything right of it — graph execution,
tool invocation, LLM calls — is LangGraph, called directly, per the governing principle.

## 3. Components

| Component | Responsibility | Tech | Interfaces |
|---|---|---|---|
| Schema parser | Load and structurally validate a YAML schema file, including its `schema_version` (`FR-1.10`, `ADR-006`) | Python, `pydantic` (or equivalent schema library) | Reads a file path, returns a typed schema object or a validation error |
| Compiler | Translate a validated schema object — including provider-agnostic LLM config (`ADR-005`) — into a LangGraph `StateGraph` | Python, `langgraph`, `langchain` (for `init_chat_model`) | Takes a schema object, returns a compiled `StateGraph` |
| Custom-code loader | Resolve a schema's `handler: module:function` references to real Python callables (`FR-1.6`) | Python `importlib` | Takes an import-path string, returns a callable; raises a clear error if unresolvable |
| CLI | User-facing entry point: `validate`, `run`, `explain` (text or JSON, `FR-3.5`) | Python, `click` or `argparse` | Reads schema file paths and flags from argv; prints to stdout/stderr |
| Canvas frontend | Read-only rendering (`FR-4.1`, Phase 2.1) and full editing (`FR-4.2`, Phase 2.2) of a compiled schema's structure | TypeScript, React, Vite, React Flow (`@xyflow/react`), `dagre` (`ADR-007`) | View-only: loads a `FR-3.5` JSON export client-side, no backend. Editing: fetches/saves against the local API server below (`ADR-007`, `ADR-008`) |
| Canvas API server (Phase 2.2) | Local, localhost-only HTTP API backing an editing session: read the current graph, validate and persist an edit (`FR-4.3`) | Python stdlib `http.server` (no new dependency) | `GET /api/graph`, `POST /api/save`; parses/validates through the same `Schema` pydantic models the CLI uses, no duplicated logic (`ADR-008`) |

No meta-agent, no backend adapter layer exists yet — see [ROADMAP](ROADMAP.md) for when each is
introduced.

## 4. Key flows

### 4.1 `agentdraft validate <schema>`
1. Parser loads the YAML file and checks it against the schema's structural rules (required fields, valid node/edge references, no orphan nodes).
2. On success: exit 0, print a confirmation.
3. On failure: exit non-zero, print the specific field/line and what's wrong — not a raw LangGraph or YAML-library stack trace.

### 4.2 `agentdraft run <schema>`
1. Parser loads and validates the schema (same as `validate`).
2. Compiler walks the schema and builds a LangGraph `StateGraph`: one LangGraph node per schema node, edges wired per the schema's routing (including conditional edges), tool bindings attached per node.
3. For any node/edge with a `handler` reference (`FR-1.6`), the custom-code loader resolves and attaches the Python callable in place of declarative config.
4. The compiled graph is invoked via LangGraph's own execution.
5. Output streams to stdout as the agent runs.

### 4.3 `agentdraft explain <schema>`
1. Parser + compiler run as in `run`, but execution is skipped.
2. The compiled graph's structure (nodes, edges, routing conditions, tool bindings) is printed as text.
3. This is a deliberate, minimal precursor to the canvas (Phase 2) — same compiled structure, text
   rendering instead of a visual one.

### 4.4 Exit codes

All CLI commands share one exit-code taxonomy (`FR-3.4`), so scripts and future MCP tool wrappers
can branch on failure class without parsing error text:

| Code | Meaning | Raised by |
|---|---|---|
| `0` | Success | Any command |
| `1` | Validation error (malformed schema, unresolved reference, unrecognized `schema_version` or provider) | `validate`, `run`, `explain` |
| `2` | Compile error (schema is structurally valid but fails to compile — e.g. an unresolvable `handler` reference) | `run`, `explain` |
| `3` | Runtime/execution error (LangGraph itself raises during `run`, e.g. a tool call or LLM call fails) | `run` |

### 4.5 `agentdraft explain <schema> --format json` + canvas (Phase 2.1)
1. Parser + compiler run as in `explain`; execution is skipped.
2. `schema_structure()` builds one structured representation of the graph (nodes, edges, routing,
   tool bindings) — the single source of truth both `explain`'s text rendering and this JSON
   output read from, so the two cannot diverge (`FR-3.5`, `ADR-007`).
3. The JSON is written to stdout (or redirected to a file by the user).
4. The canvas frontend (`canvas/`, run separately via `npm run dev`) loads that JSON file
   client-side and renders it read-only with React Flow — no backend process, no interface back
   to the Python compiler beyond the file itself (`FR-4.1`, `ADR-007`).

### 4.6 `agentdraft canvas <schema>` + canvas editing (Phase 2.2)
1. `_load_schema_or_exit` validates the schema up front; an already-invalid schema fails fast
   (exit 1) before any server starts.
2. `run_canvas_server` binds a local `ThreadingHTTPServer` (`127.0.0.1`, an OS-picked port by
   default) and prints its URL (`FR-4.3`, `ADR-008`).
3. The canvas frontend, pointed at that URL via `VITE_API_BASE`, fetches `GET /api/graph` on load
   instead of the 2.1 file picker, and renders it editable (`FR-4.2`).
4. On save, the frontend `POST`s its edited structure to `/api/save`. The server parses it via
   `schema_from_structure` into the same `Schema` pydantic model `load_schema` uses — every
   existing validation rule (`FR-1.1`-`FR-1.6`) applies with no duplicated logic.
5. Valid: `save_schema` (`FR-1.11`) writes the file, `200 {"ok": true}`. Invalid: `422
   {"errors": [...]}` with the same field-specific text the CLI prints (`format_validation_errors`,
   `FR-4.4`, `NFR-2.1`); the frontend keeps the user's in-progress edits and surfaces the errors
   rather than discarding anything.
6. `Ctrl+C` stops the server; 2.1's static/no-backend viewing mode is untouched by any of this.

## 5. Multi-tenancy & isolation

Not applicable. Single local user, no accounts, no shared state, no hosting in the current
roadmap horizon (Phase 0-3). See [PRD §2](PRD.md#2-goals--non-goals) — hosted/collab is deferred,
not excluded, but no isolation model is designed against it yet.

## 6. Scale & capacity model

Not applicable at this stage. AgentDraft runs locally, on demand, for one user, on agents small
enough to hand-author in YAML. No throughput, concurrency, or storage-volume targets exist for
Phase 1. *Assumption: revisit if a hosted/multi-user version is ever pursued (deferred per [PRD](PRD.md)).*

## 7. Failure modes & degradation

| Failure | What happens | What the user gets |
|---|---|---|
| Malformed schema (missing field, bad reference) | `validate`/`run` fails before compilation | A specific error naming the field and the problem |
| Schema references a `handler` that doesn't resolve (bad import path, missing function) | Compilation fails at the custom-code loading step | A clear import error, not a bare Python traceback |
| Schema construct not supported in Phase 1 (e.g. a memory config field) | Validation fails | An explicit "not supported in this version" error, not silent ignoring or a downstream LangGraph failure |
| LangGraph itself raises during execution (e.g. a tool call fails, an LLM call errors) | AgentDraft does not catch/reinterpret LangGraph's own runtime errors | LangGraph's native error surfaces as-is — AgentDraft is a thin compiler, not a runtime wrapper, per tenet 4 |
| LangGraph upstream breaking change | Compiler may fail against a newer LangGraph version | AgentDraft pins a tested LangGraph version per release (`ADR-003` consequence) rather than tracking latest |

There is no durability/resume story in Phase 1 (deferred per [PRD](PRD.md)) — a crashed run is not
resumable; the user re-runs `agentdraft run`.

## 8. Cross-cutting

- **Security:** the custom-code escape hatch (`FR-1.6`) executes arbitrary local Python by design —
  no sandboxing in Phase 1 (deferred, `NFR-4.1`). Acceptable because AgentDraft is local-only,
  single-user, and the author is the one authoring the schema. The canvas's local API server
  (`FR-4.3`) has no authentication either (`NFR-4.2`, `ADR-008`) — same accepted trust boundary,
  binds to `127.0.0.1` only.
- **Config/secrets:** LLM API keys and similar secrets are read from the environment (e.g.
  `OPENAI_API_KEY`), never stored in or read from the schema file itself.
- **Idempotency/consistency:** not applicable — no persisted state to keep consistent in Phase 1.

## 9. Testing & CI

**Test types:**

| Type | Target | Notes |
|---|---|---|
| Unit | Schema parser, compiler, custom-code loader | Every parser/compiler code path covered (`NFR-6.1`); this is the project's core correctness bar (`NFR-1.1`), not optional polish |
| End-to-end | `validate`/`run`/`explain` against fixture schemas | LLM calls mocked/stubbed — deterministic, free, no network dependency (`NFR-6.2`) |
| Golden-file / snapshot | `explain` output | Compiled-structure regressions show up as a diff against a committed golden file, catching unintended compiler changes in review (`NFR-6.3`) |

**CI pipeline:** lint (`ruff`), type-check (`mypy`/`pyright`), unit tests, e2e tests — all run on every
commit/PR, not only at phase boundaries (`NFR-6.4`). Gating only at phase completion would let
regressions accumulate silently between phases on a project with no fixed schedule; continuous CI
catches them where they're introduced.

Type-checking matters more here than in typical CLI glue code, because `FR-2.5`'s library API
(§3, Compiler) is a real contract — first for the CLI, later for the planned MCP server
([ROADMAP](ROADMAP.md)) — not just internal wiring.

**Structured errors, not just error messages.** Library functions raise typed exceptions (error
code + field/reference path), which the CLI renders as human-readable text (`NFR-2.1`). This
separation is tested directly: unit tests assert on the structured exception, not on stdout
formatting, so error-quality tests don't break every time CLI output wording changes.

**A phase is complete when:** CI is green *and* that phase's specific FR/NFR acceptance criteria
are met — CI passing alone is necessary but not sufficient (see [ROADMAP](ROADMAP.md) for
per-phase exit criteria).
