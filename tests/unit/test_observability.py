from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest

from agc import observability
from agc.observability import (
    _build_provider,
    _ensure_provider_configured,
    node_span,
    record_token_usage,
    run_span,
    shutdown_tracing,
)


@pytest.fixture(autouse=True)
def _reset_provider_configured_flag() -> Iterator[None]:
    """`_provider_configured` is process-global state (mirroring OTel's own
    one-shot `set_tracer_provider`) - reset it around each test so tests don't
    leak into each other within the same pytest process.
    """
    observability._provider_configured = False
    yield
    observability._provider_configured = False


def test_build_provider_returns_none_without_an_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)

    assert _build_provider() is None


def test_build_provider_returns_a_provider_when_endpoint_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "my-agent")

    provider = _build_provider()

    assert provider is not None
    assert provider.resource.attributes["service.name"] == "my-agent"


def test_build_provider_defaults_service_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)

    provider = _build_provider()

    assert provider is not None
    assert provider.resource.attributes["service.name"] == "agc"


def test_build_provider_falls_back_to_traces_specific_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://localhost:4318/v1/traces")

    assert _build_provider() is not None


def test_ensure_provider_configured_calls_build_provider_at_most_once() -> None:
    with patch("agc.observability._build_provider", return_value=None) as mock_build:
        _ensure_provider_configured()
        _ensure_provider_configured()

    mock_build.assert_called_once()


def test_shutdown_tracing_calls_shutdown_when_available() -> None:
    fake_provider = MagicMock()
    with patch("agc.observability.trace.get_tracer_provider", return_value=fake_provider):
        shutdown_tracing()

    fake_provider.shutdown.assert_called_once()


def test_shutdown_tracing_swallows_exceptions() -> None:
    fake_provider = MagicMock()
    fake_provider.shutdown.side_effect = RuntimeError("network down")
    with patch("agc.observability.trace.get_tracer_provider", return_value=fake_provider):
        shutdown_tracing()  # must not raise


def test_shutdown_tracing_noop_when_provider_has_no_shutdown() -> None:
    class NoShutdown:
        pass

    with patch("agc.observability.trace.get_tracer_provider", return_value=NoShutdown()):
        shutdown_tracing()  # must not raise


def test_record_token_usage_sets_attributes() -> None:
    span = MagicMock()

    record_token_usage(span, {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15})

    span.set_attribute.assert_any_call("agc.tokens.prompt", 10)
    span.set_attribute.assert_any_call("agc.tokens.completion", 5)
    span.set_attribute.assert_any_call("agc.tokens.total", 15)


def test_record_token_usage_noop_when_usage_is_none() -> None:
    span = MagicMock()

    record_token_usage(span, None)

    span.set_attribute.assert_not_called()


def test_record_token_usage_skips_missing_keys() -> None:
    span = MagicMock()

    record_token_usage(span, {"input_tokens": 10})

    span.set_attribute.assert_called_once_with("agc.tokens.prompt", 10)


def test_run_span_yields_a_span() -> None:
    with run_span("run-1", "schema.yaml") as span:
        assert span is not None


def test_node_span_marks_error_status_on_exception() -> None:
    with pytest.raises(ValueError, match="boom"):
        with node_span("chat"):
            raise ValueError("boom")
