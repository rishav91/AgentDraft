# Roadmap - AgentDraft

See [README](README.md) for the doc map.
MVP-first, depth before breadth
(see [PRD §2](PRD.md#2-goals--non-goals), [ARCHITECTURE tenet 3](ARCHITECTURE.md#1-design-tenets)).

**CI runs continuously from Phase 0** - lint, type-check, unit, and e2e tests gate every commit/PR,
not only phase boundaries ([ARCHITECTURE §9](ARCHITECTURE.md#9-testing--ci), `NFR-6.4`).
Each phase below additionally has its own exit criteria: CI green is necessary but not sufficient to
call a phase done.

Each sub-phase below is checked off once it has actually shipped, not once it is merely planned.
Per-sub-phase progress is the source of truth for "what's done"; the phase-level exit criteria are
the bar for calling the whole phase complete.

## Phase 0 - Walking skeleton

**Status:** Done.

**Goal:** prove schema → LangGraph compilation works at all, before investing in full Phase 1 scope.

**What ships:** the thinnest possible slice - a YAML schema for a single node, single LLM call, no
tools, no branching - compiled to a LangGraph `StateGraph` and run via a bare `agentdraft run`.
No `validate`, no `explain`, no error-quality bar yet.

**What it unlocks:** confidence that the schema → compiler → LangGraph pipeline is structurally
sound before building the rest of Phase 1 on top of it.

**Sub-phases:**

- [x] 0.1 - Single-node schema and compiler: YAML with `schema_version` and one `llm`-bearing node,
  structurally validated and compiled to a straight-line `START → node → END` `StateGraph`.
- [x] 0.2 - `agentdraft run` CLI wrapper, executed end-to-end, with a unit test on the compiler and
  an e2e test on `agentdraft run` covering it.

**Exit criteria:** CI green; the skeleton schema compiles and runs end-to-end at least once,
with a unit test on the compiler and an e2e test on `agentdraft run` covering it.

## Phase 1 - CLI (the MVP)

**Status:** Done.

**Goal:** a declarative schema expressive enough for real single-agent, tool-calling agents,
compiled to LangGraph, authored and run via CLI.

**What ships:** full scope per [requirements](requirements/system-requirements.md) P0 list -
nodes, edges, conditional routing, LLM config, tool bindings, the custom-code escape hatch
(`FR-1.6`), plus `validate`, `run`, `explain`, and field-specific error quality (`NFR-2.1`).

**What it unlocks:** a schema format stable enough to build a canvas on top of, and the first real
signal on the project's central risk - see Sequencing rationale below.

**Sub-phases:**

- [x] 1.1 - Multi-node graphs: `nodes` and `edges` sections compile to a `StateGraph` with matching
  structure (`FR-1.1`).
- [x] 1.2 - Field-level validation errors (missing fields, dangling edge references, unrecognized
  providers) and the `agentdraft validate` command (`FR-1.2`, remainder of `FR-1.3`, `FR-3.1`,
  `NFR-2.1`).
- [x] 1.3 - Tool bindings: a node's bound tools compile so the LLM can invoke them via LangGraph's
  native tool-calling mechanism (`FR-1.4`).
- [x] 1.4 - Conditional/branching edges compile to a LangGraph conditional edge with matching
  routing behavior (`FR-1.5`).
- [x] 1.5 - Custom-code escape hatch: a `handler: module:function` reference resolves to the
  callable at compile time, with a clear import error on failure (`FR-1.6`, `FR-2.2`, `ADR-004`).
- [x] 1.6 - `agentdraft explain` command and the stable, documented exit-code taxonomy across
  `validate`/`run`/`explain` (`FR-3.3`, `FR-3.4`).
- [x] 1.7 - Phase 1 exit bar: full `NFR-6.1`-`NFR-6.3` test coverage in place, and the
  schema-expressiveness metric (`PRD §6`) checked against at least one real, non-trivial agent.

**Exit criteria:** CI green; the full P0 requirements list ([requirements](requirements/system-requirements.md#p0-summary--the-phase-1-mvp))
is met, including `NFR-6.1`-`NFR-6.3` test coverage; the schema-expressiveness success metric
(`PRD §6`) has been checked against at least one real, non-trivial agent - not a toy example.

## Phase 2 - Canvas

**Status:** In progress (2.1 done; 2.2/2.3 not started).

**Goal:** see and edit an agent's graph visually - the project's actual wedge
([PRD §1](PRD.md#1-problem)) - on a schema format already proven by real Phase 1 usage.

**What ships:** a visual renderer for a compiled schema's structure (nodes, edges, routing,
tool bindings - the same structure `agentdraft explain` already prints as text), then editing
capability once viewing is solid. 2.1's stack is decided (`ADR-007`): a standalone React +
TypeScript + Vite app (`canvas/`) using React Flow, reading a static `agentdraft explain --format
json` (`FR-3.5`) export client-side - no backend process. 2.2's editing interface (how canvas
changes get written back to the schema file) is not yet decided - a Phase 2.2 planning decision,
not fixed here.

**What it unlocks:** the tool's primary value proposition actually lands. Also the second named
failure condition becomes testable: does the canvas stay in sync with everything the schema can
express, or does it drift ([PRD §7](PRD.md#7-risks))?

**Sub-phases:**

- [x] 2.1 - Read-only canvas: render a compiled schema's structure (nodes, edges, routing, tool
  bindings) with no divergence from what `agentdraft explain` prints for the same schema.
- [ ] 2.2 - Editing capability: modify a graph visually and write the changes back to the schema.
- [ ] 2.3 - Canvas CI and sync guarantee: CI extended to cover canvas code (test-tooling TBD when
  2.3 is planned; the framework itself is decided per `ADR-007`).

**Exit criteria:** CI green (extended to cover canvas code, exact test-tooling TBD when 2.3 is
planned); every construct the schema can express is renderable in the canvas, with no divergence
between what `agentdraft explain` prints and what the canvas shows for the same schema.

## Phase 3+ - Meta-agent and AgentWeave

**Status:** Not started.

Two independent, non-blocking tracks. Neither gates the other, and neither gates Phase 1/2 value.

### 3.1-3.2 - Meta-agent

Generates and iteratively refines schemas from natural-language descriptions.
Sequenced last because it's the least deterministic part of the system - it depends on Phase 1's
schema format and Phase 2's inspection surface both being stable enough to generate into and
validate against.

Current plan for the natural-language interface: an MCP server exposing AgentDraft's schema
operations (create/edit nodes and edges, validate, explain, diff a schema) as MCP tools, so an
existing agentic chat client (e.g. Claude Desktop, Claude Code) drives the iterative
natural-language refinement loop, instead of AgentDraft building and prompting a bespoke
conversational agent. This is cheap specifically because `FR-2.5` ([requirements](requirements/system-requirements.md))
keeps the compiler/schema logic in a plain library - the MCP server calls the same functions the
CLI does, rather than shelling out to the CLI or duplicating logic. Per the governing principle,
the MCP server itself is still not built until this phase starts; `FR-2.5` is the only Phase 1
concession made in anticipation of it, because it's cheap now and expensive to retrofit later.

- [ ] 3.1 - MCP server exposing AgentDraft's schema operations (create/edit nodes and edges,
  validate, explain, diff) as MCP tools, calling the same library functions as the CLI (`FR-2.5`).
- [ ] 3.2 - Iterative natural-language refinement loop validated end-to-end: a real schema, built
  via the MCP/chat loop rather than hand-authored, passes `agentdraft validate` without manual
  fixup.

**Exit criteria (meta-agent):** CI green, including tests on the MCP server's tool handlers; a
real schema, built via the MCP/chat loop rather than hand-authored, passes `agentdraft validate`
without manual fixup.

### 3.3 - AgentWeave

A custom agent SDK, pursued for learning/control over agent execution internals,
not because of a concrete LangGraph gap ([PRD §1](PRD.md#1-problem), `ADR-003`). Not on
AgentDraft's critical path. Starts whenever the author chooses to pursue it - no dependency on
meta-agent, and no fixed trigger condition beyond "the author decides to build it." Once
AgentWeave exists as a real second backend, the execution-backend interface, capability
validation, and shared skills/MCP layer (all deferred per the governing principle, [README](README.md))
get designed against two real implementations instead of one hypothetical one.

This track is intentionally left as a single unchecked item rather than split into sub-phases: its
own exit criteria (below) explicitly set no fixed scope or deadline, so a forced sub-phase
breakdown would misrepresent it as more planned than it is.

- [ ] 3.3 - AgentWeave: custom agent SDK track (exploratory, no fixed sub-phases or deadline;
  started whenever the author chooses).

**Exit criteria (AgentWeave):** none fixed - this track is exploratory and learning-driven with no
deadline or required outcome, per its own justification (`PRD §1`). It is done whenever the author
decides it's done.

## Sequencing rationale

Most deterministic first, least deterministic last - each phase retires a specific risk before the
next phase is built on top of unproven ground:

| Phase | Risk retired |
|---|---|
| 0 | Can schema → LangGraph compilation work at all? |
| 1 | Can a declarative schema capture a real single-agent, tool-calling agent without constant escape hatches? (the named Phase 1 failure condition, [PRD §7](PRD.md#7-risks)) |
| 2 | Can a canvas represent everything the schema expresses, and stay in sync with it? (the named canvas failure condition, [PRD §7](PRD.md#7-risks)) |
| 3 (meta-agent) | Can natural language reliably generate and refine valid schemas? Deliberately tackled last - it's downstream of both prior risks being retired |
| 3+ (AgentWeave) | Not a risk to AgentDraft itself - a separate, parallel learning track that also happens to eventually enable the deferred backend-abstraction work |

Building the backend-abstraction interface, capability validation, or the shared skills/MCP layer
before Phase 3+ would mean designing them against zero real alternatives to LangGraph - exactly
the premature abstraction the governing principle rules out.
