# Observability - Agentic Graph Composer

See [README](README.md) for the doc map. See [ADR-011](ADRs.md#adr-011---observability-opentelemetry-spans-around-compiled-node-functions-no-bundled-backend)
for why this is OpenTelemetry with no bundled backend, and [FR-7](requirements/system-requirements.md#fr-7--observability)
for the requirement list.

## 1. What's traced

One root span per `agc run` invocation, one child span per executed schema-defined node
(`llm`/`handler` - not the synthesized `{node}__tools` tool-execution nodes the compiler adds
internally):

| Span | Attributes |
|---|---|
| Root (`agc.run`) | `agc.run_id` (matches the [run ledger](DATA-MODEL.md#runs-agc-owned-fr-61-fr-64)'s `run_id`, `FR-7.1`), `agc.schema_path` |
| Child (`agc.node.<id>`) | `agc.node` (the node id), OTel's standard span status (`ok`/`error`, with the exception recorded on failure), and, when the node's response exposes token usage, `agc.tokens.prompt`/`agc.tokens.completion`/`agc.tokens.total` (`FR-7.2`) |

Each compiled node's function is wrapped in the span at compile time - the same extension point
`compiler.py` already uses to wrap a node for visit-tracking (`FR-1.12`) - rather than hooked in via
LangChain's callback system (`ADR-011`'s alternatives: a compiled graph's callback events include
many internal, undocumented `langsmith:hidden`-tagged sub-runs that make a callback-based filter
fragile). Agentic Graph Composer does not reimplement graph execution itself either way, per
[ARCHITECTURE tenet 4](ARCHITECTURE.md#1-design-tenets).

## 2. Correlation with the run ledger

The root span carries `agc.run_id`; every node span shares that root span's `trace_id`
(standard OTel trace/span-tree correlation, not a duplicated `run_id` attribute on every child
span - see `FR-7.1`). Any trace backend that groups by `trace_id` shows the full run, node spans
included, from that one root-span lookup. The [run ledger](DATA-MODEL.md) (`FR-6.1`) is the
always-on, zero-config local record of that same run - a trace backend is optional and external,
the ledger is not. Given a `run_id` from `agc runs show <run_id>`, the same id is the query
key into whatever OTLP backend a user has pointed Agentic Graph Composer at, if any.

## 3. Export configuration

Driven entirely by the standard OpenTelemetry SDK environment variables - no Agentic Graph Composer-specific
config file or flag exists for this (`FR-7.3`, `ADR-011`):

| Variable | Effect |
|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Unset: spans are created in-process but never exported (no-op exporter, `NFR-8.1`). Set: spans export via OTLP to that endpoint. |
| `OTEL_EXPORTER_OTLP_HEADERS` | Auth/routing headers for the OTLP endpoint (e.g. an API key for a hosted backend), same as any OTel SDK consumer |
| `OTEL_SERVICE_NAME` | Defaults to `agc`; override to distinguish multiple projects/agents in a shared backend |

## 4. Recommended self-hosted backends

Agentic Graph Composer bundles none of these - it emits standard OTLP and lets the user choose (`FR-7.4`).
Listed here as starting points, not endorsements requiring any particular one:

| Backend | Why it might fit | Notes |
|---|---|---|
| **Langfuse** | Purpose-built for LLM/agent traces: prompts, completions, token cost, per-node latency, plus an eval/scoring UI | OSS, self-hostable, has a native LangChain callback handler if a user wants deeper integration than plain OTLP |
| **Arize Phoenix** | Also purpose-built for LLM traces; can run fully local/embedded, no server to stand up for quick local inspection | Source-available (Elastic License 2.0, not OSI-approved OSS), free to self-host, OTel-native |
| **SigNoz** | General-purpose OTel-native APM (traces + metrics + logs), ClickHouse-backed | OSS, self-hostable; a good fit if a user wants Agentic Graph Composer traces alongside other services' telemetry in one place |
| **HyperDX** | Same category as SigNoz - OTel-native, ClickHouse-backed, unified traces/metrics/logs | OSS, self-hostable |

## 5. Non-goals

- No bundled trace-storage or visualization UI ([ADR-011](ADRs.md#adr-011---observability-opentelemetry-spans-around-compiled-node-functions-no-bundled-backend)) - by design, not a gap to fill later.
- No Agentic Graph Composer-specific telemetry config surface beyond standard OTel env vars - adding one would
  duplicate what the OTel SDK already standardizes.
- No cost/pricing computation inside Agentic Graph Composer itself - token-usage attributes are emitted
  (`FR-7.2`); translating them into a dollar cost is left to whatever backend a user sends spans to.
