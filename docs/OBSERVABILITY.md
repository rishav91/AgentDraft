# Observability - AgentDraft

See [README](README.md) for the doc map. See [ADR-011](ADRs.md#adr-011---observability-opentelemetry-via-langgraphlangchain-callbacks-no-bundled-backend)
for why this is OpenTelemetry with no bundled backend, and [FR-7](requirements/system-requirements.md#fr-7--observability)
for the requirement list.

## 1. What's traced

One root span per `agentdraft run` invocation, one child span per executed graph node:

| Span | Attributes |
|---|---|
| Root (`agentdraft.run`) | `agentdraft.run_id` (matches the [run ledger](DATA-MODEL.md#runs-agentdraft-owned-fr-61-fr-64)'s `run_id`, `FR-7.1`), `agentdraft.schema_path`, `agentdraft.thread_id` (if `checkpointer` configured), overall status |
| Child (`agentdraft.node.<name>`) | Node name, start/end time, status (`ok`/`error`), and, for `llm`-bearing nodes, token usage (`prompt_tokens`/`completion_tokens`/`total_tokens`) when the underlying LangChain response exposes it (`FR-7.2`) |

Instrumentation hooks into LangGraph/LangChain's own callback interface - AgentDraft does not wrap
or intercept execution itself, per [ARCHITECTURE tenet 4](ARCHITECTURE.md#1-design-tenets) (compile
to the real thing, don't reimplement it).

## 2. Correlation with the run ledger

Every span carries `agentdraft.run_id`. The [run ledger](DATA-MODEL.md) (`FR-6.1`) is the
always-on, zero-config local record of that same run - a trace backend is optional and external,
the ledger is not. Given a `run_id` from `agentdraft runs show <run_id>`, the same id is the query
key into whatever OTLP backend a user has pointed AgentDraft at, if any.

## 3. Export configuration

Driven entirely by the standard OpenTelemetry SDK environment variables - no AgentDraft-specific
config file or flag exists for this (`FR-7.3`, `ADR-011`):

| Variable | Effect |
|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Unset: spans are created in-process but never exported (no-op exporter, `NFR-8.1`). Set: spans export via OTLP to that endpoint. |
| `OTEL_EXPORTER_OTLP_HEADERS` | Auth/routing headers for the OTLP endpoint (e.g. an API key for a hosted backend), same as any OTel SDK consumer |
| `OTEL_SERVICE_NAME` | Defaults to `agentdraft`; override to distinguish multiple projects/agents in a shared backend |

## 4. Recommended self-hosted backends

AgentDraft bundles none of these - it emits standard OTLP and lets the user choose (`FR-7.4`).
Listed here as starting points, not endorsements requiring any particular one:

| Backend | Why it might fit | Notes |
|---|---|---|
| **Langfuse** | Purpose-built for LLM/agent traces: prompts, completions, token cost, per-node latency, plus an eval/scoring UI | OSS, self-hostable, has a native LangChain callback handler if a user wants deeper integration than plain OTLP |
| **Arize Phoenix** | Also purpose-built for LLM traces; can run fully local/embedded, no server to stand up for quick local inspection | OSS, OTel-native |
| **SigNoz** | General-purpose OTel-native APM (traces + metrics + logs), ClickHouse-backed | OSS, self-hostable; a good fit if a user wants AgentDraft traces alongside other services' telemetry in one place |
| **HyperDX** | Same category as SigNoz - OTel-native, ClickHouse-backed, unified traces/metrics/logs | OSS, self-hostable |

## 5. Non-goals

- No bundled trace-storage or visualization UI ([ADR-011](ADRs.md#adr-011---observability-opentelemetry-via-langgraphlangchain-callbacks-no-bundled-backend)) - by design, not a gap to fill later.
- No AgentDraft-specific telemetry config surface beyond standard OTel env vars - adding one would
  duplicate what the OTel SDK already standardizes.
- No cost/pricing computation inside AgentDraft itself - token-usage attributes are emitted
  (`FR-7.2`); translating them into a dollar cost is left to whatever backend a user sends spans to.
