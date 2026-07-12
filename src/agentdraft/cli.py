"""Thin CLI wrapper around the schema/compiler library (FR-2.5): argv
parsing and stdout formatting only, no business logic.
"""

import click
from pydantic import ValidationError

from agentdraft.compiler import compile_schema
from agentdraft.schema import Schema, load_schema


def _load_schema_or_exit(schema_path: str) -> Schema:
    """Load SCHEMA_PATH, printing field-specific errors and exiting 1 on failure."""
    try:
        return load_schema(schema_path)
    except ValidationError as exc:
        for error in exc.errors():
            msg = error["msg"].removeprefix("Value error, ")
            click.echo(f"error: {msg}", err=True)
        raise SystemExit(1) from exc


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
    graph = compile_schema(schema)
    for chunk in graph.stream({"messages": [("human", message)]}):
        for node_name, node_output in chunk.items():
            for msg in node_output["messages"]:
                click.echo(f"[{node_name}] {msg.content}")


if __name__ == "__main__":
    main()
