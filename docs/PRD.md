# PRD - Agentic Graph Composer

See [README](README.md) for the doc map and reading order.

## 1. Problem

Hand-writing a LangGraph agent means reading and reasoning about its structure as Python code:
nodes, edges, conditional routing, and state plumbing, all interleaved with the logic each node runs.
There is no way to see the shape of an agent, only its implementation.

This is felt by one person today: the author, building and iterating on agents for personal use,
with an intent to open the tool up to other developers later if it proves out.

The current workaround is reading LangGraph source and mentally reconstructing the graph, or
adding ad hoc print/logging statements to see what actually ran. Both are slow and get slower
as an agent grows past a handful of nodes.

**The wedge:** a declarative schema, compiled to a real LangGraph `StateGraph`, that can be
*seen and edited as a graph* rather than only read as code. The CLI (Phase 1) exists to stabilize
that schema against real usage; the canvas (Phase 2) is where the wedge actually lands.

## 2. Goals & non-goals

### Goals
- Define agents declaratively (YAML) instead of hand-writing LangGraph wiring code.
- Compile that schema into a real, runnable LangGraph `StateGraph` — not a simplified re-implementation.
- Make an agent's structure inspectable without reading its implementation.
- Keep the schema honest: if it can't express a real agent, that's a failure condition (§7), not something to paper over.
- Support any LLM provider LangChain supports, without Agentic Graph Composer writing per-vendor code (`ADR-005`).
- Persist and resume a crashed/interrupted run without re-running an agent from scratch (Phase 3,
  `ADR-009`).
- Track schema edit history locally, independent of whether the author uses git (Phase 3, `FR-9`).
- Record and inspect run history - status, timing, errors - for every `agc run`, with zero
  external setup required (Phase 3, `FR-6`).
- Emit standard, vendor-neutral traces for a run's execution, without Agentic Graph Composer bundling a
  specific observability backend (Phase 3, `ADR-011`).
- Catch behavioral regressions in a schema via a repeatable, deterministic eval harness (Phase 3,
  `ADR-012`).

### Non-goals

| Item | Deferred or excluded | Reason |
|---|---|---|
| Visual canvas | Deferred — Phase 2 | Depends on a schema format proven by real hand-authored usage first ([ROADMAP](ROADMAP.md)) |
| Meta-agent (NL → schema) | Deferred - Phase 4 | Least deterministic part of the system; sequenced last, after Phase 3's production hardening |
| AgentWeave (custom backend) | Deferred - Phase 4+, trigger-based | Pursued for learning/control over agent execution, not a concrete gap in LangGraph today; not on the critical path |
| Execution-backend abstraction interface | Deferred until AgentWeave exists | Governing principle ([README](README.md)): no abstraction before a second real consumer |
| Backend capability validation | Deferred until a second backend exists | Nothing to validate against with only LangGraph |
| Shared backend-neutral skills/MCP layer | Deferred until a second backend exists | Nothing to share with only one consumer |
| Sandboxed tool execution | Deferred - post-Phase 1 | Out of scope for Phase 1; not addressed by Phase 3 either |
| Multi-agent orchestration / subgraph composition | Deferred - post-Phase 1 | Out of scope for Phase 1; not addressed by Phase 3 either |
| Hosted / multi-user / auth | Deferred, not excluded | Local-first now; architecture should not preclude a hosted/collab version later |
| Swappable/pluggable DB backend for Agentic Graph Composer-owned local storage (version history, run ledger) | Deferred until a second concrete backend need exists | Governing principle extended to storage (`ADR-010`); Agentic Graph Composer-owned data is SQLite-only for now, unlike checkpointing (below), which already gets Postgres via LangGraph |
| Bundled observability backend/trace UI | Excluded by design | Agentic Graph Composer stays vendor-neutral via OTLP; users bring their own backend (`ADR-011`) |
| LLM-as-judge / semantic eval assertions | Deferred | Deterministic-only assertions for Phase 3; revisit if insufficient for agents whose main output is prose (`ADR-012`) |
| Automatic run resumption (no explicit thread_id) | Excluded by design | `--resume <thread_id>` is always explicit, so a run is never silently continued from the wrong prior attempt (`FR-5.3`) |

## 3. Personas

| Persona | Scope | Primary need |
|---|---|---|
| Agent author (the user, today) | Full access, local machine | Define, run, and inspect agents faster than hand-writing LangGraph |
| Agent author (future, if open-sourced) | Full access, local machine | Same need, once the tool is stable enough to hand to others |

No multi-tenancy, no role separation — single local user throughout the roadmap's current horizon (Phase 0-3).

## 4. Core use cases

1. **Define an agent.** Author writes a YAML schema describing a single agent: LLM config, tool bindings, nodes, conditional edges.
2. **Validate before running.** Author runs `agc validate <schema>` and gets a clear error if the schema is malformed or references an unsupported construct - not a runtime stack trace from inside LangGraph.
3. **Run an agent.** Author runs `agc run <schema>`; Agentic Graph Composer compiles the schema into a LangGraph `StateGraph` and executes it.
4. **Inspect a compiled agent.** Author runs `agc explain <schema>` to print the compiled graph's structure (nodes, edges, config) as text, without executing it - the CLI's precursor to the canvas.
5. **Escape the schema when needed.** Author references a Python callable from the schema for node/edge logic too complex to declare (§5, `FR-1.6`), instead of the schema blocking them entirely.
6. **Resume an interrupted run (Phase 3).** Author re-invokes `agc run <schema> --resume <thread_id>` after a crash or manual kill, continuing from the last persisted checkpoint instead of restarting the agent from scratch (`FR-5.3`).
7. **Inspect run history (Phase 3).** Author runs `agc runs list`/`agc runs show <run_id>` to see past runs, their status, timing, and errors, with no external tooling required (`FR-6`).
8. **Trace a run externally (Phase 3).** Author points the standard `OTEL_EXPORTER_OTLP_ENDPOINT` env var at a self-hosted backend (e.g. Langfuse) and gets per-node spans, latency, and token usage for a run, with no Agentic Graph Composer-specific config (`FR-7`).
9. **Guard against regressions (Phase 3).** Author runs `agc eval <schema> <evals.yaml>` before and after a schema edit, catching cases where the edit silently breaks a previously-passing case (`FR-8`).

## 5. Scope / governing rule

Governing principle (full statement in [README](README.md)): **never build a backend abstraction or
interface until there are two concrete, real consumers that need it.** Phase 1 and Phase 2 compile
and run directly against LangGraph, with no interface layer in between. This one rule settles the
non-goals for the backend interface, capability validation, and the shared skills/MCP layer.

Phase 1 scope (see [requirements](requirements/system-requirements.md) for the full FR/NFR list):
single-agent, tool-calling graphs only. No memory, no durability/resume, no sandboxing, no
multi-agent composition. A typed "custom code" node/edge is the one deliberate escape hatch,
so real agents aren't blocked on schema coverage gaps.

Phase 3 scope (production hardening, `FR-5`-`FR-9`): opt-in checkpointing/resume, local schema
version history, local run history, OpenTelemetry observability, and a deterministic eval harness
- all built as thin passthroughs to existing upstream capability (LangGraph's checkpointers,
OpenTelemetry's SDK) or minimal Agentic Graph Composer-owned local storage (one shared SQLite file, `ADR-010`),
not new abstractions. Sandboxing and multi-agent composition remain out of scope.

## 6. Success metrics

**Product / adoption:** N/A at this stage — single user, no adoption funnel to measure. Revisit
if/when the tool is opened to other developers (goal, not yet scheduled).

**Technical / milestone:**

| Metric | Target | How measured |
|---|---|---|
| Time-to-define a new simple agent | Measurably lower via Agentic Graph Composer schema than hand-writing the equivalent LangGraph code | Author times both paths for the same agent shape (single agent, tool-calling) |
| Schema expressiveness | Zero or near-zero escape-hatch usage for agents within Phase 1's declared scope (single-agent, tool-calling) | Track escape-hatch (`FR-1.6`) usage across agents defined during Phase 1 |
| Compiler correctness | Compiled `StateGraph` behaves identically to the hand-written equivalent for the same agent | Manual comparison during Phase 1; no automated equivalence suite planned yet |
| Durability (Phase 3) | A killed run resumes to completion without re-executing already-completed nodes | e2e test kills the process mid-run and asserts `--resume` continues from the correct checkpoint (`NFR-7.1`) |
| Eval reproducibility (Phase 3) | Two consecutive `agc eval` runs of an unchanged schema produce identical results | Asserted directly in CI (`NFR-9.1`) |

*Assumption: no fixed timeline or quantitative time-savings threshold has been set (e.g. "50% faster") — the milestone is directional (measurably lower), not numeric. Revisit once Phase 1 has real usage data.*

## 7. Risks

| Risk | Mitigation |
|---|---|
| Declarative schema can't capture real LangGraph flexibility (LangGraph allows arbitrary Python in nodes/conditional edges) — this is the named failure condition for the whole project | Validate early with a real, non-trivial agent (not a toy example) before investing in the canvas; the custom-code escape hatch (`FR-1.6`) is the deliberate release valve if the schema hits a ceiling |
| LangGraph's API evolves/breaks upstream, and the compiler targets it directly with no abstraction layer (by design, per the governing principle) | Accepted cost of the governing principle; pin a LangGraph version per Agentic Graph Composer release rather than tracking latest |
| Canvas (Phase 2) can't represent everything the schema can express, or canvas-produced schemas are hand-hostile, breaking the "one schema drives both" premise | Named as one of the project's explicit failure conditions ([README](README.md)); canvas built only after the schema format is stable from real CLI usage |
| AgentWeave never gets a concrete justification beyond "learning" and stalls indefinitely | Accepted - AgentWeave is explicitly not on Agentic Graph Composer's critical path; its absence doesn't block Phase 1 or Phase 2 value |
| Solo, side-project pace with no fixed deadline — indefinite schedule slippage | Accepted trade-off given the personal-first goal; phased roadmap ([ROADMAP](ROADMAP.md)) keeps each phase independently valuable regardless of pace |
| Checkpoint resume covers graph *state* only, not real-world side effects of already-executed custom-code nodes (e.g. a tool that already sent an email) - resuming could re-trigger effects the author didn't expect (Phase 3) | Explicit `--resume <thread_id>` UX (not automatic) puts the decision in the author's hands each time; documented as an accepted caveat, same trust boundary as the custom-code escape hatch (`ADR-004`, `ADR-009`) |
| A single shared SQLite file becomes a bottleneck or corruption risk if a future feature adds concurrent multi-process access (Phase 3) | Scoped explicitly to the single-local-user model (`ADR-010`); revisit if a hosted/multi-user version is ever pursued (already a deferred, not excluded, non-goal above) |
