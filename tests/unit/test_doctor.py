from pathlib import Path

from agc.doctor import (
    check_checkpointer_dsn,
    check_extra_installed,
    check_otel_endpoint,
    check_provider_key,
    check_python_version,
    run_checks,
)
from agc.schema import load_schema

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_check_python_version_ok() -> None:
    check = check_python_version()
    assert check.ok
    assert "Python" in check.message


def test_check_provider_key_present(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    check = check_provider_key("anthropic")
    assert check.ok
    assert "ANTHROPIC_API_KEY" in check.message
    assert "sk-test" not in check.message


def test_check_provider_key_missing(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    check = check_provider_key("openai")
    assert not check.ok
    assert "OPENAI_API_KEY" in check.message


def test_check_provider_key_unknown_provider_is_non_blocking() -> None:
    check = check_provider_key("some-other-provider")
    assert check.ok
    assert "verify manually" in check.message


def test_check_checkpointer_dsn_present(monkeypatch) -> None:
    monkeypatch.setenv("MY_DSN", "postgresql://...")
    check = check_checkpointer_dsn("MY_DSN")
    assert check.ok
    assert "MY_DSN" in check.message
    assert "postgresql" not in check.message


def test_check_checkpointer_dsn_missing(monkeypatch) -> None:
    monkeypatch.delenv("MY_DSN", raising=False)
    check = check_checkpointer_dsn("MY_DSN")
    assert not check.ok


def test_check_otel_endpoint_never_fails(monkeypatch) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    assert check_otel_endpoint().ok

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    assert check_otel_endpoint().ok


def test_check_extra_installed_found() -> None:
    check = check_extra_installed("click", "dev")
    assert check.ok
    assert "installed" in check.message


def test_check_extra_installed_missing() -> None:
    check = check_extra_installed("no_such_module_xyz", "examples")
    assert not check.ok
    assert 'pip install "agentic-graph-composer[examples]"' in check.message


def test_run_checks_with_no_schema_is_general_only() -> None:
    checks = run_checks(None)
    messages = [c.message for c in checks]
    assert any("Python" in m for m in messages)
    assert not any("API_KEY" in m for m in messages)


def test_run_checks_dedupes_providers_across_nodes(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    schema = load_schema(str(FIXTURES / "multi_node.yaml"))
    checks = run_checks(schema)
    provider_key_checks = [c for c in checks if "ANTHROPIC_API_KEY" in c.message]
    assert len(provider_key_checks) == 1


def test_run_checks_includes_checkpointer_dsn_and_postgres_extra(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.delenv("MY_POSTGRES_DSN", raising=False)
    schema = load_schema(str(FIXTURES / "checkpointed_postgres.yaml"))
    checks = run_checks(schema)
    messages = [c.message for c in checks]
    assert any("MY_POSTGRES_DSN" in m for m in messages)
    assert any("psycopg" in m for m in messages)


def test_run_checks_sqlite_checkpointer_has_no_dsn_check(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    schema = load_schema(str(FIXTURES / "checkpointed.yaml"))
    checks = run_checks(schema)
    messages = [c.message for c in checks]
    assert not any("dsn_env" in m for m in messages)
