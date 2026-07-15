# System Requirements - Agentic Graph Composer

See [README](../README.md) for the doc map. Scope matches [PRD §5](../PRD.md#5-scope--governing-rule)
and [ARCHITECTURE](../ARCHITECTURE.md). IDs are stable once assigned — append, don't renumber.

## Functional requirements

### FR-1 — Schema

| ID | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| FR-1.1 | Schema expresses a single-agent graph: nodes and edges | P0 | A YAML file with `nodes:` and `edges:` sections compiles to a LangGraph `StateGraph` with matching structure |
| FR-1.2 | Schema parser structurally validates a schema and reports field-level errors | P0 | An invalid schema (missing required field, dangling edge reference) fails `validate`/`run` with an error naming the specific field and problem — not a raw YAML or library traceback |
| FR-1.3 | Schema expresses per-node LLM config, provider-agnostic: explicit `provider` and `model` fields mapped onto LangChain's existing multi-provider interface, plus prompt/system message and parameters (`ADR-005`) | P0 | A node's LLM config compiles to the corresponding LangChain chat model instance for the specified provider; an unrecognized provider name fails validation with a field-specific error, not a deep LangChain stack trace |
| FR-1.4 | Schema expresses tool bindings (function-calling tools) per node | P0 | A node with bound tools compiles so the LLM can invoke them per LangGraph's native tool-calling mechanism |
| FR-1.5 | Schema expresses conditional/branching edges | P0 | A schema with a conditional edge compiles to a LangGraph conditional edge with matching routing behavior |
| FR-1.6 | Schema supports a typed "custom code" node/edge referencing a user-supplied Python callable (`handler: module:function`) | P0 | A schema node/edge with a `handler` field resolves to the referenced callable at compile time (`ADR-004`); an unresolvable reference fails with a clear import error, not a bare traceback |
| FR-1.7 | Schema expresses memory/persistence config (checkpointers) | Superseded | Out of scope for Phase 1; superseded by `FR-5` (Phase 3 - [ROADMAP](../ROADMAP.md)), which specifies the actual `checkpointer` block (`ADR-009`) |
| FR-1.8 | Schema expresses sandboxing config for tool execution | P2 — deferred | Out of scope for Phase 1; see `NFR-4.1` |
| FR-1.9 | Schema expresses multi-agent/subgraph composition | P2 — deferred | Out of scope for Phase 1 |
| FR-1.10 | Schema includes a required `schema_version` field identifying the Agentic Graph Composer schema format version it targets (`ADR-006`) | P0 | Phase 1 schemas declare `schema_version: 1`; a missing or unrecognized version fails validation with a specific error naming the expected version, not a generic parse failure |
| FR-1.11 | A `Schema` object serializes back to YAML text, the inverse of `load_schema` | P0 | `dump_schema`/`schema_to_yaml` round-trip a loaded schema back to YAML without introducing fields the original didn't use (no `edges:` for an implicit single-node schema, no empty `tools:` on a handler node); the canvas's save path (`FR-4.3`) is built on this |
| FR-1.12 | A conditional edge may declaratively cap how many times its source node executes before the compiler forces a fallback route, bounding self-loops (e.g. reflection/self-correction cycles) | P1 | A conditional edge may set `max_visits` (positive integer) and `fallback` (a key in `routes`) alongside `condition`/`routes`; both fields required together, `fallback` validated against `routes` at parse time. Once the source node has executed `max_visits` times, the compiler forces the `fallback` route on the next evaluation instead of calling `condition` again - no hand-written counting logic needed in the condition function |

### FR-2 — Compiler

| ID | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| FR-2.1 | Compile a validated schema into a real LangGraph `StateGraph` | P0 | Compiler output is a `StateGraph` instance usable by LangGraph's own execution — not a re-implementation |
| FR-2.2 | Resolve custom-code `handler` references at compile time | P0 | See `FR-1.6` acceptance criteria |
| FR-2.3 | Compiled graph's runtime behavior matches the hand-written LangGraph equivalent for the same agent shape | P0 | Manual comparison during Phase 1 (`PRD §6`); no automated equivalence suite planned yet |
| FR-2.4 | Compiler targets a pinned, tested LangGraph version per Agentic Graph Composer release | P1 | Agentic Graph Composer's packaging declares an exact or narrow-range LangGraph dependency version |
| FR-2.5 | Compiler and schema operations (load, validate, compile, explain) are exposed as a plain Python library API, not embedded in CLI command handlers | P0 | `agc validate/run/explain` are thin wrappers that parse argv and call library functions; no business logic lives in the argument-parsing/command-handler code. Enables a future MCP server (`ROADMAP` Phase 4) to call the same functions instead of shelling out to or duplicating the CLI |

### FR-3 — CLI

| ID | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| FR-3.1 | `agc validate <schema>` checks a schema without executing it | P0 | Exits 0 with a confirmation on a valid schema; exits non-zero with a field-level error (`FR-1.2`) on an invalid one |
| FR-3.2 | `agc run <schema>` compiles and executes a schema | P0 | Runs the compiled graph via LangGraph's execution; streams output to stdout; exits non-zero on compile or runtime failure |
| FR-3.3 | `agc explain <schema>` prints the compiled graph's structure as text, without executing | P0 | Output lists nodes, edges, routing conditions, and tool bindings; no LLM/tool calls are made |
| FR-3.4 | CLI commands use a stable, documented exit-code taxonomy | P0 | `0` success, `1` validation error, `2` compile error, `3` runtime/execution error ([ARCHITECTURE §4.4](../ARCHITECTURE.md#44-exit-codes)); every failure path in `validate`/`run`/`explain` exits with the correct code, asserted directly in e2e tests (`NFR-6.2`) |
| FR-3.5 | `agc explain <schema> --format json` prints the compiled graph's structure as machine-readable JSON, without executing | P0 | Same structure as `FR-3.3`'s text output (nodes, edges, routing conditions, tool bindings), rendered from the same underlying data (`schema_structure`) so text and JSON cannot diverge; this is the canvas's sole data source (`FR-4.1`, `ADR-007`) |

### FR-4 — Canvas

| ID | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| FR-4.1 | Read-only canvas renders a compiled schema's structure (nodes, edges, routing, tool bindings) | P0 | Loading a `FR-3.5` JSON export into the canvas renders every node and edge the schema expresses, with no divergence from what `agc explain` prints for the same schema ([ROADMAP](../ROADMAP.md) Phase 2.1 exit criterion) |
| FR-4.2 | Canvas supports full editing parity with schema expressiveness: add/remove/edit nodes (llm ↔ handler, provider/model/system, tools) and their outgoing edges (direct or conditional+routes) | P0 | Every construct `FR-1.1`-`FR-1.6` can express is both renderable (`FR-4.1`) and editable in the canvas; editing is node-centric — a node's outgoing routing is edited as a single direct-target-list-or-conditional-block unit, matching `Schema`'s own XOR shape (`schema.py`'s `Edge` model) |
| FR-4.3 | `agc canvas <schema>` starts a local, localhost-only HTTP API exposing the current graph (`GET /api/graph`) and a validated save endpoint (`POST /api/save`) for the canvas frontend (`ADR-008`) | P0 | A save request is parsed through the same `Schema` pydantic model `load_schema` uses (`schema_from_structure`, `FR-1.11`'s `save_schema`), so every existing validation rule applies with no duplicated logic; a valid save writes the file, an invalid one leaves it unchanged |
| FR-4.4 | Canvas save validation errors surface as field-specific messages in the UI, not raw server errors | P0 | An invalid save (`FR-4.3`) returns HTTP 422 with the same field-specific error text `format_validation_errors` produces for CLI errors (`NFR-2.1`); the canvas displays them without discarding the user's in-progress edits |
| FR-4.5 | Canvas suggests known `module:function` callables for `handler`, `condition`, and `tools` reference fields, and previews the selected one's source | P1 | `GET /api/callables` statically scans the project (no import/execution) for module-level function definitions and returns `module:function` candidates as autocomplete suggestions, not a closed dropdown - a reference the scanner misses (e.g. dynamically defined) can still be typed by hand. `GET /api/source?ref=...` returns the exact original source text of a discovered callable (via `ast.get_source_segment`, still no import) for read-only preview - the canvas never writes to Python files, preserving the schema/logic separation (`ADR-004`, `ARCHITECTURE` tenet 2). Agentic Graph Composer's own installed package is always excluded from results; `agc canvas --scan-dir <path>` (repeatable) restricts which subdirectories are scanned, so e.g. a project's `tests/` directory can be left out of suggestions without affecting real imports. Module paths always resolve relative to the true import root (cwd), independent of which subdirectories were scanned, so a suggested reference always matches what would actually resolve at compile time |
| FR-4.6 | Canvas offers a closed dropdown for a node's `llm.provider` field | P1 | `GET /api/providers` returns `schema.SUPPORTED_PROVIDERS`, the same sorted list `Schema`'s validation checks a provider against (`FR-1.3`, `ADR-005`) - so the dropdown can never offer (or silently drift from) a value a save would reject. Unlike `FR-4.5`'s callable fields, this is a genuinely closed/enumerable set, so a real `<select>` is appropriate rather than free-text autocomplete; `model` stays free text, since no reliable enumerable model registry exists across providers |
| FR-4.7 | Canvas can switch which schema file an already-running editing session targets, without restarting `agc canvas` | P1 | `GET /api/schemas` statically scans the project (same exclusion rules as `FR-4.5`) for `.yaml`/`.yml` files and reports each one's validity/node count plus which is currently active; `POST /api/open` (a relative or absolute path) validates and loads the requested file through the same `Schema` model `FR-4.3` uses, then retargets subsequent `GET /api/graph`/`POST /api/save` calls at it - the server's `import_root` and discovery scope stay fixed, only the active schema file changes |

### FR-5 - Persistence & checkpointing

| ID | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| FR-5.1 | Schema may declare an optional `checkpointer` block (`backend: sqlite \| postgres`, backend-specific connection info) enabling LangGraph-native checkpointing for a run (`ADR-009`) | P0 | The compiler passes the corresponding LangGraph checkpointer (`SqliteSaver`/`PostgresSaver`) to `StateGraph.compile()`; a `postgres` backend reads its connection string from an environment variable reference, never inline in the schema, per the existing secrets convention (`CLAUDE.md`) |
| FR-5.2 | `agc run <schema>` without `--resume` starts a new checkpoint thread when `checkpointer` is configured | P0 | A fresh `thread_id` is generated per run and recorded in the run ledger (`FR-6.1`); checkpoints persist to the configured backend as the graph executes |
| FR-5.3 | `agc run <schema> --resume <thread_id>` resumes an interrupted or failed run from its last persisted checkpoint | P0 | Execution continues from the last completed node for that `thread_id` rather than re-running the graph from `START`; an unknown/nonexistent `thread_id` fails with a specific error, not a bare LangGraph traceback |
| FR-5.4 | Default checkpointer backend is SQLite, written to the shared local store (`ADR-010`) | P0 | A schema with `checkpointer: {backend: sqlite}` (or `backend` omitted while `checkpointer` is present) persists to `.agc/state.db` with no additional configuration |
| FR-5.5 | A schema with no `checkpointer` block runs exactly as before - opt-in, not a breaking change | P0 | Existing Phase 1/2 schemas with no `checkpointer` field validate and run identically to today; `--resume` on such a schema fails with a clear "no checkpointer configured" error rather than a silent no-op |
| FR-5.6 | `agc run --resume <thread_id>` fails if the schema has changed since that thread's most recently recorded run, unless `--force` is passed (`ADR-014`) | P0 | Resume compares the current schema file's content hash against the hash recorded for the most recent prior run of that `thread_id`; a mismatch fails with a specific error before any execution, not a silent resume against a different compiled graph; `--force` bypasses the check; the guard is skipped (not enforced) when no prior run is recorded for that `thread_id` |

### FR-6 - Run history

| ID | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| FR-6.1 | Every `agc run` invocation is recorded in the local run ledger: run id, schema path, schema content hash, `thread_id` (if `checkpointer` configured), status, start/end time, per-node timings, error (if any) | P0 | A run row exists in `runs` ([DATA-MODEL](../DATA-MODEL.md)) after every `agc run` invocation, success or failure, including runs killed mid-execution (status `interrupted`, best-effort - see `NFR-7.1`) |
| FR-6.2 | `agc runs list [schema]` lists past runs with status and duration, optionally filtered to one schema path | P1 | Output is sorted most-recent-first; each row shows run id, schema path, status, started/duration |
| FR-6.3 | `agc runs show <run_id>` prints full detail for one run: per-node timings, error, and `thread_id` if resumable | P1 | Output includes enough to construct the exact `agc run <schema> --resume <thread_id>` command if the run is resumable |
| FR-6.4 | `agc runs prune [--older-than <duration>] [--keep-last <n>]` deletes run-ledger entries on explicit request only | P2 | No automatic/background deletion of run history; pruning never touches checkpoint rows still needed to resume a run that hasn't completed |

### FR-7 - Observability

| ID | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| FR-7.1 | Compiled graph execution emits OpenTelemetry spans: one root span per run, one child span per node (start/end, latency, status), correlated with the run ledger's run id (`ADR-011`) | P0 | Running a schema with an OTLP endpoint configured produces a trace whose root span carries an `agc.run_id` attribute matching `FR-6.1`'s ledger row, and one child span per executed node sharing that root span's `trace_id` (OTel's own trace/span-tree correlation - not a duplicated `run_id` attribute on every child span) |
| FR-7.2 | Token usage (prompt/completion/total) is captured as span attributes for LLM-bearing nodes, when the underlying LangChain response exposes it | P1 | A node's span includes token-usage attributes whenever the provider's response includes usage metadata; absent for providers/responses that don't expose it, not a hard failure |
| FR-7.3 | Span export is OTLP-based and driven entirely by standard OpenTelemetry environment variables (`OTEL_EXPORTER_OTLP_ENDPOINT`, etc.) | P0 | With no `OTEL_EXPORTER_OTLP_ENDPOINT` set, spans are created but exported nowhere (no-op exporter, `NFR-8.1`); setting the standard env var(s) is sufficient to export, with no Agentic Graph Composer-specific config file or flag needed |
| FR-7.4 | Agentic Graph Composer bundles no observability backend | P0 | [OBSERVABILITY.md](../OBSERVABILITY.md) documents self-hosted options (Langfuse, SigNoz, HyperDX, Arize Phoenix) a user may point OTLP at; none is a runtime dependency of `agc` itself |

### FR-8 - Eval harness

| ID | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| FR-8.1 | An evals file (YAML) lists named cases against one schema: an initial state input and one or more assertions on final state (`ADR-012`) | P0 | A malformed evals file (missing `schema`/`cases`, unresolvable schema path) fails `agc eval` with a field-specific error before any case runs, matching `NFR-2.1`'s error-quality bar |
| FR-8.2 | `agc eval <schema> <evals-file>` compiles the schema once and runs every case, reporting pass/fail per case | P0 | Output names each case and whether it passed; a run summary (N passed / M failed) prints at the end |
| FR-8.3 | Assertion types are deterministic and structural: field equality, substring, regex, evaluated against final graph state via a dotted/indexed path | P0 | Each assertion type is covered by at least one unit test; no assertion type invokes an LLM or any non-deterministic check |
| FR-8.4 | Exit code `4` is appended to the CLI's exit-code taxonomy: one or more eval assertions failed | P0 | `agc eval` exits `4` if every case ran to completion but at least one assertion failed; exits `1`/`2`/`3` for evals-file/schema validation, compile, or runtime errors respectively (same taxonomy as `run`); exits `0` only if every case's every assertion passed |

### FR-9 - Schema version history

| ID | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| FR-9.1 | Every `save_schema` call records a new revision of that schema file's content to the local store (`ADR-010`) | P0 | Saving a schema (CLI or canvas `POST /api/save`, `FR-4.3`) appends a `schema_versions` row (path, content hash, full YAML snapshot, timestamp); a save that doesn't change the file's content does not create a duplicate revision |
| FR-9.2 | `agc schema log <schema>` lists recorded revisions for a schema path, most recent first | P1 | Output shows revision number, timestamp, and content hash for each recorded save |
| FR-9.3 | `agc schema diff <schema> <rev-a> <rev-b>` shows a text diff between two recorded revisions | P1 | Output is a standard unified diff of the two revisions' YAML text; also usable as the diff primitive the Phase 4+ meta-agent's MCP tools plan to expose ([ROADMAP](../ROADMAP.md) 4.1) |
| FR-9.4 | Schema version history is local-only, distinct from `schema_version` (`ADR-006`) | P0 | Revision numbers here track edit history of one file over time; `schema_version` (`FR-1.10`) remains the unrelated schema-*format* version field - no field or command conflates the two |
| FR-9.5 | `agc schema revert <schema> <rev>` restores the working file to a recorded revision's content, appending it as a new revision (`ADR-013`) | P1 | The working file's content is replaced with `rev`'s recorded content and (unless it's already identical to the current tip) recorded as a new, higher-numbered revision; existing revisions are never deleted, reordered, or overwritten - reverting to any past revision, including one made "current" again by a later revert, remains possible indefinitely; an out-of-range revision fails with the same "no revision N" error as `schema diff` |

## Non-functional requirements

| ID | Requirement | Priority | Quantified target |
|---|---|---|---|
| NFR-1.1 | Correctness: compiled graph behavior matches hand-written LangGraph equivalent | P0 | Zero known behavioral divergence for any agent shape within Phase 1 scope (single-agent, tool-calling) |
| NFR-2.1 | Error quality: validation/compile errors are field-specific, not raw library tracebacks | P0 | Every `FR-1.2`/`FR-1.6` failure path names the offending field or reference in its error message |
| NFR-3.1 | Coupling: compiler targets a single pinned LangGraph version per release, not "latest" | P1 | Declared dependency is an exact or narrow version range, verified in packaging config |
| NFR-4.1 | Security: no sandboxing of custom-code (`FR-1.6`) execution in Phase 1 | P0 (accepted, not mitigated) | Documented as an accepted risk: local-only, single-user, author-authored code only ([ARCHITECTURE §8](../ARCHITECTURE.md#8-cross-cutting)) |
| NFR-4.2 | Security: the canvas's local API server (`FR-4.3`) has no authentication | P0 (accepted, not mitigated) | Same trust boundary as `NFR-4.1`: local-only, single-user, binds to `127.0.0.1` only, no remote reachability by design (`ADR-008`) |
| NFR-5.1 | Responsiveness: `validate`/`explain` complete fast enough for interactive, iterative schema authoring | P1 | *Assumption: sub-2-second target for agents of the size hand-authored in Phase 1 (single-digit node counts); no formal benchmark suite yet — revisit if agents grow larger* |
| NFR-6.1 | Testability: schema parser and compiler modules have unit test coverage | P0 | Every parser/compiler code path has at least one unit test; no PR merges without passing tests ([ARCHITECTURE §9](../ARCHITECTURE.md#9-testing--ci)) |
| NFR-6.2 | Testability: CLI commands (`validate`/`run`/`explain`) have end-to-end tests against fixture schemas | P0 | Fixture schemas cover each Phase 1 schema construct (`FR-1.1`-`FR-1.6`); LLM calls are mocked/stubbed, not live, so tests stay deterministic and free |
| NFR-6.3 | Testability: `explain` output is covered by golden-file/snapshot tests | P1 | A compiled-structure regression changes a committed golden file's diff, making unintended compiler changes visible in review |
| NFR-6.4 | CI: lint, type-check, and the full test suite run on every commit/PR, not only at phase boundaries | P0 | CI pipeline fails the build on any lint, type, or test failure; a phase is not considered complete unless CI is green *and* that phase's specific FR/NFR acceptance criteria are met |
| NFR-7.1 | Durability: a run with `checkpointer` configured is resumable from its last completed node after the process is killed or crashes | P0 | An e2e test kills the `agc run` process mid-execution (`SIGKILL`) and asserts `--resume <thread_id>` continues from the correct checkpoint without re-executing already-completed nodes |
| NFR-7.2 | Durability: the default SQLite checkpointer/local-store backend has no server process or network dependency | P1 | `checkpointer: {backend: sqlite}` (or the default) works fully offline, with no reachable service beyond the local filesystem |
| NFR-8.1 | Observability overhead: span creation performs no network I/O when no OTLP endpoint is configured | P1 | With `OTEL_EXPORTER_OTLP_ENDPOINT` unset, a run produces no outbound network calls attributable to tracing (verified by test double/no-op exporter assertion) |
| NFR-9.1 | Eval determinism: two consecutive `agc eval` runs of the same evals file against an unchanged schema produce identical pass/fail results for all deterministic assertions | P1 | Re-running `agc eval` twice in CI with no schema change yields the same exit code and per-case results both times |

## P0 summary — the Phase 1 MVP

- **Schema:** single-agent graphs with nodes, edges, conditional routing, provider-agnostic LLM config, tool bindings, a custom-code escape hatch, and a required `schema_version` field (`FR-1.1`-`FR-1.6`, `FR-1.10`).
- **Compiler:** produces a real LangGraph `StateGraph`; behaviorally matches the hand-written equivalent (`FR-2.1`-`FR-2.3`); exposed as a library, not baked into CLI command handlers (`FR-2.5`).
- **CLI:** `validate`, `run`, `explain`, with a stable exit-code taxonomy (`FR-3.1`-`FR-3.4`).
- **Quality bar:** field-specific errors everywhere (`NFR-2.1`); no behavioral divergence from hand-written LangGraph (`NFR-1.1`); unit + e2e tests green in CI on every commit (`NFR-6.1`-`NFR-6.4`).

Everything marked P2 - deferred (sandboxing, multi-agent) is explicitly out of the Phase 1
MVP; see [ROADMAP](../ROADMAP.md) for when each is picked back up.

## P3 summary - the Phase 3 production-hardening scope

- **Persistence & checkpointing:** opt-in `checkpointer` block, SQLite default / Postgres available,
  explicit `--resume <thread_id>` (`FR-5.1`-`FR-5.5`, `ADR-009`), guarded by a schema-consistency
  check that fails resume if the schema changed since that thread's last run (`FR-5.6`, `ADR-014`).
- **Run history:** every run recorded to a local ledger; `agc runs list`/`show`/`prune`
  (`FR-6.1`-`FR-6.4`).
- **Observability:** OpenTelemetry spans per run/node, OTLP export via standard env vars, no
  bundled backend (`FR-7.1`-`FR-7.4`, `ADR-011`).
- **Eval harness:** `agc eval <schema> <evals-file>`, deterministic assertions only, exit
  code `4` on assertion failure (`FR-8.1`-`FR-8.4`, `ADR-012`).
- **Schema version history:** every save recorded as a revision, browsable via `agc schema
  log`/`diff`/`revert` (`FR-9.1`-`FR-9.5`), distinct from the `schema_version` format field
  (`ADR-006`); revert is additive, never destroying or reordering revisions (`ADR-013`).
- **Storage:** all Agentic Graph Composer-owned local state (versions, run ledger, default checkpoints) in one
  shared SQLite file, no DB abstraction (`ADR-010`).

See [ROADMAP](../ROADMAP.md) Phase 3 for sub-phase sequencing, starting with checkpointing.
