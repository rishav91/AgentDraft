# PRD — AgentDraft

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
- Support any LLM provider LangChain supports, without AgentDraft writing per-vendor code (`ADR-005`).

### Non-goals

| Item | Deferred or excluded | Reason |
|---|---|---|
| Visual canvas | Deferred — Phase 2 | Depends on a schema format proven by real hand-authored usage first ([ROADMAP](ROADMAP.md)) |
| Meta-agent (NL → schema) | Deferred — Phase 3 | Least deterministic part of the system; sequenced last |
| AgentWeave (custom backend) | Deferred — Phase 3+, trigger-based | Pursued for learning/control over agent execution, not a concrete gap in LangGraph today; not on the critical path |
| Execution-backend abstraction interface | Deferred until AgentWeave exists | Governing principle ([README](README.md)): no abstraction before a second real consumer |
| Backend capability validation | Deferred until a second backend exists | Nothing to validate against with only LangGraph |
| Shared backend-neutral skills/MCP layer | Deferred until a second backend exists | Nothing to share with only one consumer |
| Memory / persistence / checkpointing | Deferred — post-Phase 1 | Excluded from the Phase 1 schema to keep the compiler's first target small (§5) |
| Sandboxed tool execution | Deferred — post-Phase 1 | Same reason |
| Multi-agent orchestration / subgraph composition | Deferred — post-Phase 1 | Same reason |
| Hosted / multi-user / auth | Deferred, not excluded | Local-first now; architecture should not preclude a hosted/collab version later |
| Tracing UI | Deferred — likely alongside or after canvas | No canvas to host it in yet |

## 3. Personas

| Persona | Scope | Primary need |
|---|---|---|
| Agent author (the user, today) | Full access, local machine | Define, run, and inspect agents faster than hand-writing LangGraph |
| Agent author (future, if open-sourced) | Full access, local machine | Same need, once the tool is stable enough to hand to others |

No multi-tenancy, no role separation — single local user throughout the roadmap's current horizon (Phase 0-3).

## 4. Core use cases

1. **Define an agent.** Author writes a YAML schema describing a single agent: LLM config, tool bindings, nodes, conditional edges.
2. **Validate before running.** Author runs `agentdraft validate <schema>` and gets a clear error if the schema is malformed or references an unsupported construct — not a runtime stack trace from inside LangGraph.
3. **Run an agent.** Author runs `agentdraft run <schema>`; AgentDraft compiles the schema into a LangGraph `StateGraph` and executes it.
4. **Inspect a compiled agent.** Author runs `agentdraft explain <schema>` to print the compiled graph's structure (nodes, edges, config) as text, without executing it — the CLI's precursor to the canvas.
5. **Escape the schema when needed.** Author references a Python callable from the schema for node/edge logic too complex to declare (§5, `FR-1.6`), instead of the schema blocking them entirely.

## 5. Scope / governing rule

Governing principle (full statement in [README](README.md)): **never build a backend abstraction or
interface until there are two concrete, real consumers that need it.** Phase 1 and Phase 2 compile
and run directly against LangGraph, with no interface layer in between. This one rule settles the
non-goals for the backend interface, capability validation, and the shared skills/MCP layer.

Phase 1 scope (see [requirements](requirements/system-requirements.md) for the full FR/NFR list):
single-agent, tool-calling graphs only. No memory, no durability/resume, no sandboxing, no
multi-agent composition. A typed "custom code" node/edge is the one deliberate escape hatch,
so real agents aren't blocked on schema coverage gaps.

## 6. Success metrics

**Product / adoption:** N/A at this stage — single user, no adoption funnel to measure. Revisit
if/when the tool is opened to other developers (goal, not yet scheduled).

**Technical / milestone:**

| Metric | Target | How measured |
|---|---|---|
| Time-to-define a new simple agent | Measurably lower via AgentDraft schema than hand-writing the equivalent LangGraph code | Author times both paths for the same agent shape (single agent, tool-calling) |
| Schema expressiveness | Zero or near-zero escape-hatch usage for agents within Phase 1's declared scope (single-agent, tool-calling) | Track escape-hatch (`FR-1.6`) usage across agents defined during Phase 1 |
| Compiler correctness | Compiled `StateGraph` behaves identically to the hand-written equivalent for the same agent | Manual comparison during Phase 1; no automated equivalence suite planned yet |

*Assumption: no fixed timeline or quantitative time-savings threshold has been set (e.g. "50% faster") — the milestone is directional (measurably lower), not numeric. Revisit once Phase 1 has real usage data.*

## 7. Risks

| Risk | Mitigation |
|---|---|
| Declarative schema can't capture real LangGraph flexibility (LangGraph allows arbitrary Python in nodes/conditional edges) — this is the named failure condition for the whole project | Validate early with a real, non-trivial agent (not a toy example) before investing in the canvas; the custom-code escape hatch (`FR-1.6`) is the deliberate release valve if the schema hits a ceiling |
| LangGraph's API evolves/breaks upstream, and the compiler targets it directly with no abstraction layer (by design, per the governing principle) | Accepted cost of the governing principle; pin a LangGraph version per AgentDraft release rather than tracking latest |
| Canvas (Phase 2) can't represent everything the schema can express, or canvas-produced schemas are hand-hostile, breaking the "one schema drives both" premise | Named as one of the project's explicit failure conditions ([README](README.md)); canvas built only after the schema format is stable from real CLI usage |
| AgentWeave never gets a concrete justification beyond "learning" and stalls indefinitely | Accepted — AgentWeave is explicitly not on AgentDraft's critical path; its absence doesn't block Phase 1 or Phase 2 value |
| Solo, side-project pace with no fixed deadline — indefinite schedule slippage | Accepted trade-off given the personal-first goal; phased roadmap ([ROADMAP](ROADMAP.md)) keeps each phase independently valuable regardless of pace |
