# AgentDraft — Design Docs

## What this is

AgentDraft is a CLI- and canvas-first builder for AI agents on LangGraph: agents are defined as a
declarative YAML schema, compiled into a real LangGraph `StateGraph`, rather than hand-written as
graph code. The single most important scope decision: **the build is phased and each phase is
independently valuable** — a CLI (schema + compiler, Phase 1), then a canvas (Phase 2, the
project's actual wedge — see [PRD](PRD.md)), then a meta-agent and an optional custom backend
(AgentWeave), pursued later and not gating anything before them.

## Governing principle

**Never build a backend abstraction or interface until there are two concrete, real consumers that
need it.** AgentDraft compiles and runs directly against LangGraph — no execution-backend
interface, no backend-capability validation, no backend-neutral skills/MCP layer — until AgentWeave
exists as a real second backend and forces the seam (`ADR-003`). Every "should we abstract X?"
question in this project is settled by this rule.

| | In (now) | Deferred (until AgentWeave is real) |
|---|---|---|
| Backend | Compile/run directly against LangGraph | Execution-backend interface, capability validation |
| Tools | N/A — no second backend to be neutral toward | Backend-neutral skills/MCP layer |

## Locked stack / key constraints

- **Language:** Python (`ADR-002`)
- **Schema format:** YAML (`ADR-001`), with a required `schema_version` field (`ADR-006`)
- **Escape hatch:** typed custom-code node/edge referencing a user-supplied Python callable, for logic the schema can't declare (`ADR-004`)
- **LLM provider:** agnostic — schema's `provider`/`model` fields map onto LangChain's existing multi-provider interface, not an AgentDraft-built abstraction (`ADR-005`)
- **Deployment:** local-first, single-user, no auth/hosting/multi-tenancy in the current roadmap horizon — architecture stays open to a hosted/collab version later, not designed against it yet
- **Team:** solo, side-project pace, no fixed deadline

## Document map

| Doc | Purpose |
|---|---|
| [PRD.md](PRD.md) | Problem, personas, goals/non-goals, use cases, success metrics, risks |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Design tenets, component breakdown, key flows, failure modes |
| [ADRs.md](ADRs.md) | Schema format, language, no-backend-abstraction, and escape-hatch decisions |
| [requirements/system-requirements.md](requirements/system-requirements.md) | FR/NFR with stable IDs, P0 = the Phase 1 MVP |
| [ROADMAP.md](ROADMAP.md) | Phase 0 through Phase 3+, sequencing rationale, risk retired per phase |

Deliberately not in this suite yet: a Data Model doc (schema entities are simple enough to cover
inline in ARCHITECTURE), API Contracts (no external API — CLI only), Observability (no tracing UI
until a canvas exists to host it), and AI Architecture (no AI/ML surface exists until the Phase 3
meta-agent). Add these when the phase that needs them starts.

## Reading order

1. [PRD.md](PRD.md) — why this exists, what it is and isn't
2. [ARCHITECTURE.md](ARCHITECTURE.md) — how Phase 1 is built
3. [ADRs.md](ADRs.md) — why the key decisions were made this way
4. [requirements/system-requirements.md](requirements/system-requirements.md) — the exact Phase 1 contract
5. [ROADMAP.md](ROADMAP.md) — what's next, and why in this order

## Conventions

- `FR-x.y` functional requirements, `NFR-x.y` non-functional, `ADR-00N` decisions. IDs are stable
  once assigned — append, don't renumber.
- Non-goals in [PRD §2](PRD.md#2-goals--non-goals) are the single source of truth for what's
  deferred vs. excluded; every other doc stays consistent with it rather than restating it.
- Docs cross-link with relative markdown links; no doc duplicates another's content.
