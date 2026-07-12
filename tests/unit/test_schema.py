from pathlib import Path

import pytest
from pydantic import ValidationError

from agentdraft.schema import Schema, load_schema

FIXTURE = Path(__file__).parent.parent / "fixtures" / "skeleton.yaml"
MULTI_NODE_FIXTURE = Path(__file__).parent.parent / "fixtures" / "multi_node.yaml"


def test_load_schema_parses_fixture() -> None:
    schema = load_schema(FIXTURE)

    assert schema.schema_version == 1
    assert len(schema.nodes) == 1
    assert schema.nodes[0].id == "chat"
    assert schema.nodes[0].llm.provider == "anthropic"


def test_load_schema_parses_multi_node_fixture() -> None:
    schema = load_schema(MULTI_NODE_FIXTURE)

    assert [node.id for node in schema.nodes] == ["greeter", "closer"]
    assert [(edge.from_, edge.to) for edge in schema.edges] == [
        ("START", "greeter"),
        ("greeter", "closer"),
        ("closer", "END"),
    ]


def test_rejects_unsupported_schema_version() -> None:
    with pytest.raises(ValidationError, match="schema_version"):
        Schema.model_validate(
            {
                "schema_version": 99,
                "nodes": [{"id": "chat", "llm": {"provider": "anthropic", "model": "x"}}],
            }
        )


def test_rejects_zero_nodes() -> None:
    with pytest.raises(ValidationError, match="at least one node"):
        Schema.model_validate({"schema_version": 1, "nodes": []})


def test_rejects_duplicate_node_ids() -> None:
    with pytest.raises(ValidationError, match="duplicate node id 'a'"):
        Schema.model_validate(
            {
                "schema_version": 1,
                "nodes": [
                    {"id": "a", "llm": {"provider": "anthropic", "model": "x"}},
                    {"id": "a", "llm": {"provider": "anthropic", "model": "x"}},
                ],
            }
        )


def test_rejects_multi_node_without_edges() -> None:
    with pytest.raises(ValidationError, match="edges: required"):
        Schema.model_validate(
            {
                "schema_version": 1,
                "nodes": [
                    {"id": "a", "llm": {"provider": "anthropic", "model": "x"}},
                    {"id": "b", "llm": {"provider": "anthropic", "model": "x"}},
                ],
            }
        )


def test_rejects_dangling_edge_reference() -> None:
    with pytest.raises(ValidationError, match="unknown node 'ghost'"):
        Schema.model_validate(
            {
                "schema_version": 1,
                "nodes": [{"id": "a", "llm": {"provider": "anthropic", "model": "x"}}],
                "edges": [{"from": "a", "to": "ghost"}],
            }
        )


def test_rejects_unrecognized_provider() -> None:
    with pytest.raises(ValidationError, match="unrecognized provider 'not-a-real-provider'"):
        Schema.model_validate(
            {
                "schema_version": 1,
                "nodes": [{"id": "chat", "llm": {"provider": "not-a-real-provider", "model": "x"}}],
            }
        )
