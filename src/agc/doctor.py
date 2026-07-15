"""Environment/readiness checks (3.5.3): presence-only checks (never values,
per this repo's secrets convention) against the env vars and optional extras
a schema would actually need at run time - surfaced proactively here instead
of failing mid-`agc run`.
"""

import importlib.util
import os
import sys
from dataclasses import dataclass

from agc.init import PROVIDER_API_KEY_ENV
from agc.schema import Schema

#: provider -> (extra name, the module its client library installs as).
#: Only covers providers `agc init` ships templates for - not
#: exhaustive against every provider `schema.py`'s SUPPORTED_PROVIDERS
#: accepts. Providers outside PROVIDER_API_KEY_ENV are reported as unknown,
#: not silently skipped.
PROVIDER_EXTRA = {
    "anthropic": ("examples", "langchain_anthropic"),
    "openai": ("examples", "langchain_openai"),
}


@dataclass(frozen=True)
class Check:
    ok: bool
    message: str


def check_python_version() -> Check:
    ok = sys.version_info >= (3, 11)
    version = ".".join(str(part) for part in sys.version_info[:3])
    return Check(ok, f"Python {version} (requires >=3.11)")


def check_provider_key(provider: str) -> Check:
    env_var = PROVIDER_API_KEY_ENV.get(provider)
    if env_var is None:
        return Check(
            True,
            f"provider {provider!r} has no known API key env var to check here "
            "(not anthropic/openai) - verify manually",
        )
    present = bool(os.environ.get(env_var))
    if present:
        return Check(True, f"{env_var}: set")
    return Check(False, f"{env_var}: not set")


def check_checkpointer_dsn(dsn_env: str) -> Check:
    present = bool(os.environ.get(dsn_env))
    if present:
        return Check(True, f"{dsn_env}: set (checkpointer.dsn_env)")
    return Check(False, f"{dsn_env}: not set (checkpointer.dsn_env)")


def check_otel_endpoint() -> Check:
    # Informational only - observability.py already degrades gracefully with
    # no endpoint configured (no-op exporter), so this never fails doctor.
    present = bool(
        os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        or os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    )
    if present:
        return Check(True, "OTEL_EXPORTER_OTLP_ENDPOINT: set (tracing enabled)")
    return Check(True, "OTEL_EXPORTER_OTLP_ENDPOINT: not set (tracing disabled, not an error)")


def check_extra_installed(module_name: str, extra_name: str) -> Check:
    found = importlib.util.find_spec(module_name) is not None
    if found:
        return Check(True, f"{module_name}: installed")
    return Check(
        False, f'{module_name}: missing - pip install "agentic-graph-composer[{extra_name}]"'
    )


def run_checks(schema: Schema | None) -> list[Check]:
    """Run every applicable check for SCHEMA (or just the general ones if None)."""
    checks = [check_python_version(), check_otel_endpoint()]
    if schema is None:
        return checks

    seen_providers: set[str] = set()
    for node in schema.nodes:
        if node.llm is None or node.llm.provider in seen_providers:
            continue
        seen_providers.add(node.llm.provider)
        checks.append(check_provider_key(node.llm.provider))
        extra = PROVIDER_EXTRA.get(node.llm.provider)
        if extra is not None:
            extra_name, module_name = extra
            checks.append(check_extra_installed(module_name, extra_name))

    if schema.checkpointer is not None and schema.checkpointer.backend == "postgres":
        assert schema.checkpointer.dsn_env is not None  # enforced by Checkpointer's validator
        checks.append(check_checkpointer_dsn(schema.checkpointer.dsn_env))
        checks.append(check_extra_installed("psycopg", "postgres"))

    return checks
