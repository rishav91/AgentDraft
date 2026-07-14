"""OpenTelemetry instrumentation for a run's execution (`FR-7`, `ADR-011`).
Vendor-neutral: AgentDraft emits standard OTel spans and bundles no backend of
its own (`FR-7.4`) - export is driven entirely by the standard
`OTEL_EXPORTER_OTLP_ENDPOINT` env var (`FR-7.3`), with zero AgentDraft-specific
config surface. With no endpoint configured, `opentelemetry-api`'s own default
tracer provider creates spans that are never recorded or exported (`NFR-8.1`):
zero network I/O, near-zero overhead.

Each compiled node is wrapped with `node_span` at compile time (`compiler.py`),
rather than hooked in via LangChain's callback system - LangGraph's internal
callback events include many `langsmith:hidden`-tagged sub-runs with no stable
node-name attribute at the top level, which would make a callback-based filter
fragile and version-coupled. Wrapping the same node function `compiler.py`
already wraps for visit-tracking (`FR-1.12`) gets an equally "real" per-node
span with none of that fragility.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span, Status, StatusCode

_TRACER_NAME = "agentdraft"
_EXPORT_TIMEOUT_SECONDS = 5

_provider_configured = False


def _build_provider() -> TracerProvider | None:
    """Pure factory: a configured `TracerProvider` if OTLP export should be
    enabled (`FR-7.3`), or `None` if it should stay no-op. Touches no global
    state - callers decide whether/how to install it.
    """
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or os.environ.get(
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"
    )
    if not endpoint:
        return None

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    service_name = os.environ.get("OTEL_SERVICE_NAME", "agentdraft")
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(timeout=_EXPORT_TIMEOUT_SECONDS))
    )
    return provider


def _ensure_provider_configured() -> None:
    """Install a real provider at most once per process (OTel's own global
    tracer provider can only be set once - a second call is a silently-ignored
    no-op upstream, so this guard exists purely to skip the wasted work of
    re-evaluating env vars on every run within one process, not to work around
    that restriction).
    """
    global _provider_configured
    if _provider_configured:
        return
    _provider_configured = True
    provider = _build_provider()
    if provider is not None:  # pragma: no cover - exercised via manual OTLP smoke test,
        trace.set_tracer_provider(provider)  # not CI: a real provider install is process-global


def _tracer() -> trace.Tracer:
    _ensure_provider_configured()
    return trace.get_tracer(_TRACER_NAME)


def shutdown_tracing() -> None:
    """Best-effort flush of any configured provider before the process exits, so
    pending spans are actually sent. Never raises - tracing must never block or
    fail a run (ARCHITECTURE §7's failure-mode for an unreachable OTLP endpoint).
    """
    provider = trace.get_tracer_provider()
    shutdown = getattr(provider, "shutdown", None)
    if shutdown is None:
        return
    try:
        shutdown()
    except Exception:
        pass


@contextmanager
def run_span(run_id: str, schema_path: str) -> Iterator[Span]:
    """Root span for one `agentdraft run` invocation (`FR-7.1`)."""
    with _tracer().start_as_current_span("agentdraft.run") as span:
        span.set_attribute("agentdraft.run_id", run_id)
        span.set_attribute("agentdraft.schema_path", schema_path)
        yield span


@contextmanager
def node_span(node_id: str) -> Iterator[Span]:
    """Child span for one executed node (`FR-7.1`). Must be entered while a
    `run_span` is the current span for OTel's own context propagation to nest it
    correctly - `compiler.py` only wraps nodes this way for compiled graphs
    invoked from `agentdraft run`, which always opens a `run_span` first.
    """
    with _tracer().start_as_current_span(f"agentdraft.node.{node_id}") as span:
        span.set_attribute("agentdraft.node", node_id)
        try:
            yield span
        except Exception as exc:
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            span.record_exception(exc)
            raise
        else:
            span.set_status(Status(StatusCode.OK))


def record_token_usage(span: Span, usage: Mapping[str, Any] | None) -> None:
    """Attach token-usage attributes to SPAN from USAGE (`FR-7.2`) - a no-op if
    the node's LLM response didn't expose usage metadata.
    """
    if not usage:
        return
    for key, attr in (
        ("input_tokens", "agentdraft.tokens.prompt"),
        ("output_tokens", "agentdraft.tokens.completion"),
        ("total_tokens", "agentdraft.tokens.total"),
    ):
        value = usage.get(key)
        if value is not None:
            span.set_attribute(attr, value)
