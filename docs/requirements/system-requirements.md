# System Requirements — AgentDraft (Phase 1)

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

## Non-functional requirements

| ID | Requirement | Priority | Quantified target |
|---|---|---|---|
| NFR-1.1 | Correctness: compiled graph behavior matches hand-written LangGraph equivalent | P0 | Zero known behavioral divergence for any agent shape within Phase 1 scope (single-agent, tool-calling) |
| NFR-2.1 | Error quality: validation/compile errors are field-specific, not raw library tracebacks | P0 | Every `FR-1.2`/`FR-1.6` failure path names the offending field or reference in its error message |
| NFR-3.1 | Coupling: compiler targets a single pinned LangGraph version per release, not "latest" | P1 | Declared dependency is an exact or narrow version range, verified in packaging config |
| NFR-4.1 | Security: no sandboxing of custom-code (`FR-1.6`) execution in Phase 1 | P0 (accepted, not mitigated) | Documented as an accepted risk: local-only, single-user, author-authored code only ([ARCHITECTURE §8](../ARCHITECTURE.md#8-cross-cutting)) |
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
