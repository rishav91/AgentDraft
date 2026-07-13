# System Requirements — AgentDraft

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
| FR-1.7 | Schema expresses memory/persistence config (checkpointers) | P2 — deferred | Out of scope for Phase 1 ([PRD §2](../PRD.md#2-goals--non-goals)); tracked here for future-phase planning only |
| FR-1.8 | Schema expresses sandboxing config for tool execution | P2 — deferred | Out of scope for Phase 1; see `NFR-4.1` |
| FR-1.9 | Schema expresses multi-agent/subgraph composition | P2 — deferred | Out of scope for Phase 1 |
| FR-1.10 | Schema includes a required `schema_version` field identifying the AgentDraft schema format version it targets (`ADR-006`) | P0 | Phase 1 schemas declare `schema_version: 1`; a missing or unrecognized version fails validation with a specific error naming the expected version, not a generic parse failure |
| FR-1.11 | A `Schema` object serializes back to YAML text, the inverse of `load_schema` | P0 | `dump_schema`/`schema_to_yaml` round-trip a loaded schema back to YAML without introducing fields the original didn't use (no `edges:` for an implicit single-node schema, no empty `tools:` on a handler node); the canvas's save path (`FR-4.3`) is built on this |
| FR-1.12 | A conditional edge may declaratively cap how many times its source node executes before the compiler forces a fallback route, bounding self-loops (e.g. reflection/self-correction cycles) | P1 | A conditional edge may set `max_visits` (positive integer) and `fallback` (a key in `routes`) alongside `condition`/`routes`; both fields required together, `fallback` validated against `routes` at parse time. Once the source node has executed `max_visits` times, the compiler forces the `fallback` route on the next evaluation instead of calling `condition` again - no hand-written counting logic needed in the condition function |

### FR-2 — Compiler

| ID | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| FR-2.1 | Compile a validated schema into a real LangGraph `StateGraph` | P0 | Compiler output is a `StateGraph` instance usable by LangGraph's own execution — not a re-implementation |
| FR-2.2 | Resolve custom-code `handler` references at compile time | P0 | See `FR-1.6` acceptance criteria |
| FR-2.3 | Compiled graph's runtime behavior matches the hand-written LangGraph equivalent for the same agent shape | P0 | Manual comparison during Phase 1 (`PRD §6`); no automated equivalence suite planned yet |
| FR-2.4 | Compiler targets a pinned, tested LangGraph version per AgentDraft release | P1 | AgentDraft's packaging declares an exact or narrow-range LangGraph dependency version |
| FR-2.5 | Compiler and schema operations (load, validate, compile, explain) are exposed as a plain Python library API, not embedded in CLI command handlers | P0 | `agentdraft validate/run/explain` are thin wrappers that parse argv and call library functions; no business logic lives in the argument-parsing/command-handler code. Enables a future MCP server (`ROADMAP` Phase 3) to call the same functions instead of shelling out to or duplicating the CLI |

### FR-3 — CLI

| ID | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| FR-3.1 | `agentdraft validate <schema>` checks a schema without executing it | P0 | Exits 0 with a confirmation on a valid schema; exits non-zero with a field-level error (`FR-1.2`) on an invalid one |
| FR-3.2 | `agentdraft run <schema>` compiles and executes a schema | P0 | Runs the compiled graph via LangGraph's execution; streams output to stdout; exits non-zero on compile or runtime failure |
| FR-3.3 | `agentdraft explain <schema>` prints the compiled graph's structure as text, without executing | P0 | Output lists nodes, edges, routing conditions, and tool bindings; no LLM/tool calls are made |
| FR-3.4 | CLI commands use a stable, documented exit-code taxonomy | P0 | `0` success, `1` validation error, `2` compile error, `3` runtime/execution error ([ARCHITECTURE §4.4](../ARCHITECTURE.md#44-exit-codes)); every failure path in `validate`/`run`/`explain` exits with the correct code, asserted directly in e2e tests (`NFR-6.2`) |
| FR-3.5 | `agentdraft explain <schema> --format json` prints the compiled graph's structure as machine-readable JSON, without executing | P0 | Same structure as `FR-3.3`'s text output (nodes, edges, routing conditions, tool bindings), rendered from the same underlying data (`schema_structure`) so text and JSON cannot diverge; this is the canvas's sole data source (`FR-4.1`, `ADR-007`) |

### FR-4 — Canvas

| ID | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| FR-4.1 | Read-only canvas renders a compiled schema's structure (nodes, edges, routing, tool bindings) | P0 | Loading a `FR-3.5` JSON export into the canvas renders every node and edge the schema expresses, with no divergence from what `agentdraft explain` prints for the same schema ([ROADMAP](../ROADMAP.md) Phase 2.1 exit criterion) |
| FR-4.2 | Canvas supports full editing parity with schema expressiveness: add/remove/edit nodes (llm ↔ handler, provider/model/system, tools) and their outgoing edges (direct or conditional+routes) | P0 | Every construct `FR-1.1`-`FR-1.6` can express is both renderable (`FR-4.1`) and editable in the canvas; editing is node-centric — a node's outgoing routing is edited as a single direct-target-list-or-conditional-block unit, matching `Schema`'s own XOR shape (`schema.py`'s `Edge` model) |
| FR-4.3 | `agentdraft canvas <schema>` starts a local, localhost-only HTTP API exposing the current graph (`GET /api/graph`) and a validated save endpoint (`POST /api/save`) for the canvas frontend (`ADR-008`) | P0 | A save request is parsed through the same `Schema` pydantic model `load_schema` uses (`schema_from_structure`, `FR-1.11`'s `save_schema`), so every existing validation rule applies with no duplicated logic; a valid save writes the file, an invalid one leaves it unchanged |
| FR-4.4 | Canvas save validation errors surface as field-specific messages in the UI, not raw server errors | P0 | An invalid save (`FR-4.3`) returns HTTP 422 with the same field-specific error text `format_validation_errors` produces for CLI errors (`NFR-2.1`); the canvas displays them without discarding the user's in-progress edits |
| FR-4.5 | Canvas suggests known `module:function` callables for `handler`, `condition`, and `tools` reference fields, and previews the selected one's source | P1 | `GET /api/callables` statically scans the project (no import/execution) for module-level function definitions and returns `module:function` candidates as autocomplete suggestions, not a closed dropdown - a reference the scanner misses (e.g. dynamically defined) can still be typed by hand. `GET /api/source?ref=...` returns the exact original source text of a discovered callable (via `ast.get_source_segment`, still no import) for read-only preview - the canvas never writes to Python files, preserving the schema/logic separation (`ADR-004`, `ARCHITECTURE` tenet 2). AgentDraft's own installed package is always excluded from results; `agentdraft canvas --scan-dir <path>` (repeatable) restricts which subdirectories are scanned, so e.g. a project's `tests/` directory can be left out of suggestions without affecting real imports. Module paths always resolve relative to the true import root (cwd), independent of which subdirectories were scanned, so a suggested reference always matches what would actually resolve at compile time |
| FR-4.6 | Canvas offers a closed dropdown for a node's `llm.provider` field | P1 | `GET /api/providers` returns `schema.SUPPORTED_PROVIDERS`, the same sorted list `Schema`'s validation checks a provider against (`FR-1.3`, `ADR-005`) - so the dropdown can never offer (or silently drift from) a value a save would reject. Unlike `FR-4.5`'s callable fields, this is a genuinely closed/enumerable set, so a real `<select>` is appropriate rather than free-text autocomplete; `model` stays free text, since no reliable enumerable model registry exists across providers |

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

## P0 summary — the Phase 1 MVP

- **Schema:** single-agent graphs with nodes, edges, conditional routing, provider-agnostic LLM config, tool bindings, a custom-code escape hatch, and a required `schema_version` field (`FR-1.1`-`FR-1.6`, `FR-1.10`).
- **Compiler:** produces a real LangGraph `StateGraph`; behaviorally matches the hand-written equivalent (`FR-2.1`-`FR-2.3`); exposed as a library, not baked into CLI command handlers (`FR-2.5`).
- **CLI:** `validate`, `run`, `explain`, with a stable exit-code taxonomy (`FR-3.1`-`FR-3.4`).
- **Quality bar:** field-specific errors everywhere (`NFR-2.1`); no behavioral divergence from hand-written LangGraph (`NFR-1.1`); unit + e2e tests green in CI on every commit (`NFR-6.1`-`NFR-6.4`).

Everything marked P2 — deferred (memory, sandboxing, multi-agent) is explicitly out of the Phase 1
MVP; see [ROADMAP](../ROADMAP.md) for when each is picked back up.
