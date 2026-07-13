"""Thin CLI wrapper around the schema/compiler library (FR-2.5): argv
parsing and stdout formatting only, no business logic.

Exit codes (FR-3.4, ARCHITECTURE §4.4): 0 success, 1 validation error,
2 compile error, 3 runtime/execution error.
"""

import json
import traceback
from pathlib import Path

import click
from langgraph.graph.state import CompiledStateGraph
from pydantic import ValidationError

from agentdraft.compiler import CompileError, compile_schema, explain_schema, schema_structure
from agentdraft.schema import Schema, format_validation_errors, load_schema
from agentdraft.server import run_canvas_server


def _load_schema_or_exit(schema_path: str) -> Schema:
    """Load SCHEMA_PATH, printing field-specific errors and exiting 1 on failure."""
    try:
        return load_schema(schema_path)
    except ValidationError as exc:
        for msg in format_validation_errors(exc):
            click.echo(f"error: {msg}", err=True)
        raise SystemExit(1) from exc


def _compile_or_exit(schema: Schema) -> CompiledStateGraph:
    """Compile SCHEMA, printing a clean message and exiting 2 on a compile error."""
    try:
        return compile_schema(schema)
    except CompileError as exc:
        click.echo(f"error: {exc}", err=True)
        raise SystemExit(2) from None


@click.group()
def main() -> None:
    """AgentDraft: define agents as YAML, compile them to LangGraph."""


@main.command()
@click.argument("schema_path", type=click.Path(exists=True, dir_okay=False))
def validate(schema_path: str) -> None:
    """Validate SCHEMA_PATH without executing it."""
    _load_schema_or_exit(schema_path)
    click.echo(f"{schema_path}: valid")


@main.command()
@click.argument("schema_path", type=click.Path(exists=True, dir_okay=False))
@click.argument("message")
def run(schema_path: str, message: str) -> None:
    """Compile SCHEMA_PATH and run it with an initial human MESSAGE."""
    schema = _load_schema_or_exit(schema_path)
    graph = _compile_or_exit(schema)
    try:
        for chunk in graph.stream({"messages": [("human", message)]}):
            for node_name, node_output in chunk.items():
                for msg in node_output["messages"]:
                    click.echo(f"[{node_name}] {msg.content}")
    except Exception:
        # LangGraph's own runtime error surfaces as-is (ARCHITECTURE §7) - only the
        # exit code is AgentDraft's to control.
        traceback.print_exc()
        raise SystemExit(3) from None


@main.command()
@click.argument("schema_path", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format: human-readable text (default), or machine-readable JSON (FR-3.5), "
    "the data source for the canvas (ADR-007).",
)
def explain(schema_path: str, output_format: str) -> None:
    """Print SCHEMA_PATH's compiled structure, without executing it."""
    schema = _load_schema_or_exit(schema_path)
    try:
        if output_format == "json":
            compile_schema(schema)
            click.echo(json.dumps(schema_structure(schema), indent=2))
        else:
            click.echo(explain_schema(schema))
    except CompileError as exc:
        click.echo(f"error: {exc}", err=True)
        raise SystemExit(2) from None


@main.command()
@click.argument("schema_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--port", type=int, default=0, help="Port to bind (default: an OS-picked free port).")
def canvas(schema_path: str, port: int) -> None:
    """Start the local editing API for SCHEMA_PATH, for the canvas frontend (FR-4.3)."""
    _load_schema_or_exit(schema_path)  # fail fast on an already-invalid schema
    run_canvas_server(Path(schema_path), port=port)  # pragma: no cover - see test_server.py


if __name__ == "__main__":
    main()
