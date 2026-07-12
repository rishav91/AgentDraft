"""Thin CLI wrapper around the schema/compiler library (FR-2.5): argv
parsing and stdout formatting only, no business logic.
"""

import click

from agentdraft.compiler import compile_schema
from agentdraft.schema import load_schema


@click.group()
def main() -> None:
    """AgentDraft: define agents as YAML, compile them to LangGraph."""


@main.command()
@click.argument("schema_path", type=click.Path(exists=True, dir_okay=False))
@click.argument("message")
def run(schema_path: str, message: str) -> None:
    """Compile SCHEMA_PATH and run it with an initial human MESSAGE."""
    schema = load_schema(schema_path)
    graph = compile_schema(schema)
    for chunk in graph.stream({"messages": [("human", message)]}):
        for node_name, node_output in chunk.items():
            for msg in node_output["messages"]:
                click.echo(f"[{node_name}] {msg.content}")


if __name__ == "__main__":
    main()
