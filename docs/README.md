# AgentDraft — Design Docs

## What this is

AgentDraft is a CLI- and canvas-first builder for AI agents on LangGraph: agents are defined as a
declarative YAML schema, compiled into a real LangGraph `StateGraph`, rather than hand-written as
graph code. The single most important scope decision: **the build is phased and each phase is
independently valuable** — a CLI (schema + compiler, Phase 1), then a canvas (Phase 2, the
project's actual wedge - see [PRD](PRD.md)), then production hardening (Phase 3: checkpointing,
version/run history, observability, evals), then a meta-agent and an optional custom backend
(AgentWeave, Phase 4+), pursued later and not gating anything before them.

## Governing principle

**Never build a backend abstraction or interface until there are two concrete, real consumers that
need it.** AgentDraft compiles and runs directly against LangGraph — no execution-backend
interface, no backend-capability validation, no backend-neutral skills/MCP layer — until AgentWeave
exists as a real second backend and forces the seam (`ADR-003`). This extends to AgentDraft-owned
local storage (`ADR-010`): no swappable-DB abstraction until a second concrete backend need exists.
Where an upstream library already provides multi-backend support with real consumers - LangChain's
provider registry (`ADR-005`), LangGraph's checkpointers (`ADR-009`) - a thin passthrough config
field is not the abstraction this principle rules out. Every "should we abstract X?" question in
this project is settled by this rule.

| | In (now) | Deferred (until a second real consumer) |
|---|---|---|
| Execution backend | Compile/run directly against LangGraph | Execution-backend interface, capability validation (until AgentWeave is real) |
| Tools | N/A - no second backend to be neutral toward | Backend-neutral skills/MCP layer (until AgentWeave is real) |
| Checkpointing | LangGraph's own `SqliteSaver`/`PostgresSaver`, exposed via a config field (`ADR-009`) | An AgentDraft-built checkpoint format - never planned |
| AgentDraft-owned local storage (version history, run ledger) | One shared SQLite file (`ADR-010`) | A swappable-DB abstraction (until a second backend need exists) |
| Observability sink | Standard OTLP export (`ADR-011`) | A bundled trace-storage/UI backend - excluded by design, not deferred |

## Locked stack / key constraints

- **Language:** Python (`ADR-002`)
- **Schema format:** YAML (`ADR-001`), with a required `schema_version` field (`ADR-006`)
- **Escape hatch:** typed custom-code node/edge referencing a user-supplied Python callable, for logic the schema can't declare (`ADR-004`)
- **LLM provider:** agnostic — schema's `provider`/`model` fields map onto LangChain's existing multi-provider interface, not an AgentDraft-built abstraction (`ADR-005`)
- **Deployment:** local-first, single-user, no auth/hosting/multi-tenancy in the current roadmap horizon — architecture stays open to a hosted/collab version later, not designed against it yet
- **Local persistence:** stdlib `sqlite3`, one shared file, no ORM (`ADR-010`); checkpointing additionally supports Postgres via LangGraph's own checkpointer (`ADR-009`)
- **Observability:** OpenTelemetry SDK for instrumentation; no bundled backend (`ADR-011`)
- **Team:** solo, side-project pace, no fixed deadline

## Document map

| Doc | Purpose |
|---|---|
| [PRD.md](PRD.md) | Problem, personas, goals/non-goals, use cases, success metrics, risks |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Design tenets, component breakdown, key flows, failure modes |
| [ADRs.md](ADRs.md) | Schema format, language, no-backend-abstraction, escape-hatch, persistence, and observability decisions |
| [DATA-MODEL.md](DATA-MODEL.md) | The shared local SQLite store: `schema_versions`, `runs`, and their relation to LangGraph's own checkpoint tables |
| [OBSERVABILITY.md](OBSERVABILITY.md) | What's traced, span shape, run-ledger correlation, recommended self-hosted OTel backends |
| [requirements/system-requirements.md](requirements/system-requirements.md) | FR/NFR with stable IDs, P0 = the Phase 1 MVP, P3 = the production-hardening scope |
| [ROADMAP.md](ROADMAP.md) | Phase 0 through Phase 4+, sequencing rationale, risk retired per phase |

Deliberately not in this suite yet: API Contracts (no external API - CLI only) and AI Architecture
(no AI/ML surface exists until the Phase 4 meta-agent). Add these when the phase that needs them
starts.

## Reading order

1. [PRD.md](PRD.md) — why this exists, what it is and isn't
2. [ARCHITECTURE.md](ARCHITECTURE.md) - how the system is built
3. [ADRs.md](ADRs.md) — why the key decisions were made this way
4. [requirements/system-requirements.md](requirements/system-requirements.md) - the exact contract, per phase
5. [DATA-MODEL.md](DATA-MODEL.md) and [OBSERVABILITY.md](OBSERVABILITY.md) - Phase 3's persistence and tracing detail
6. [ROADMAP.md](ROADMAP.md) - what's next, and why in this order

## Conventions

- `FR-x.y` functional requirements, `NFR-x.y` non-functional, `ADR-00N` decisions. IDs are stable
  once assigned — append, don't renumber.
- Non-goals in [PRD §2](PRD.md#2-goals--non-goals) are the single source of truth for what's
  deferred vs. excluded; every other doc stays consistent with it rather than restating it.
- Docs cross-link with relative markdown links; no doc duplicates another's content.
