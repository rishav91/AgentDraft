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


def test_rejects_edge_from_unknown_node() -> None:
    with pytest.raises(ValidationError, match="'from' references unknown node 'ghost'"):
        Schema.model_validate(
            {
                "schema_version": 1,
                "nodes": [{"id": "a", "llm": {"provider": "anthropic", "model": "x"}}],
                "edges": [{"from": "ghost", "to": "a"}],
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


def _two_node_schema_dict(edges: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "nodes": [
            {"id": "a", "llm": {"provider": "anthropic", "model": "x"}},
            {"id": "b", "llm": {"provider": "anthropic", "model": "x"}},
        ],
        "edges": edges,
    }


def test_parses_conditional_edge() -> None:
    schema = Schema.model_validate(
        _two_node_schema_dict(
            [{"from": "a", "condition": "tests.support.routing:by_last_message_content",
              "routes": {"positive": "b", "negative": "END"}}]
        )
    )

    edge = schema.edges[0]
    assert edge.condition == "tests.support.routing:by_last_message_content"
    assert edge.routes == {"positive": "b", "negative": "END"}


def test_rejects_edge_with_both_to_and_condition() -> None:
    with pytest.raises(ValidationError, match="sets both 'to' and 'condition'"):
        Schema.model_validate(
            _two_node_schema_dict(
                [{"from": "a", "to": "b", "condition": "x:y", "routes": {"k": "b"}}]
            )
        )


def test_rejects_edge_with_neither_to_nor_condition() -> None:
    with pytest.raises(ValidationError, match="sets neither 'to' nor 'condition'"):
        Schema.model_validate(_two_node_schema_dict([{"from": "a"}]))


def test_rejects_conditional_edge_missing_routes() -> None:
    with pytest.raises(ValidationError, match="requires both 'condition' and a non-empty 'routes'"):
        Schema.model_validate(_two_node_schema_dict([{"from": "a", "condition": "x:y"}]))


def test_rejects_conditional_edge_with_dangling_route_target() -> None:
    with pytest.raises(ValidationError, match="routes\\['k'\\].*unknown node 'ghost'"):
        Schema.model_validate(
            _two_node_schema_dict(
                [{"from": "a", "condition": "x:y", "routes": {"k": "ghost"}}]
            )
        )


def test_rejects_conditional_edge_alongside_another_edge_from_same_source() -> None:
    with pytest.raises(ValidationError, match="'a' has a conditional edge"):
        Schema.model_validate(
            _two_node_schema_dict(
                [
                    {"from": "a", "condition": "x:y", "routes": {"k": "b"}},
                    {"from": "a", "to": "b"},
                ]
            )
        )


def test_parses_handler_node() -> None:
    schema = Schema.model_validate(
        {
            "schema_version": 1,
            "nodes": [{"id": "shout", "handler": "tests.support.handlers:uppercase_last_message"}],
        }
    )

    assert schema.nodes[0].llm is None
    assert schema.nodes[0].handler == "tests.support.handlers:uppercase_last_message"


def test_rejects_node_with_both_llm_and_handler() -> None:
    with pytest.raises(ValidationError, match="sets both 'llm' and 'handler'"):
        Schema.model_validate(
            {
                "schema_version": 1,
                "nodes": [
                    {
                        "id": "chat",
                        "llm": {"provider": "anthropic", "model": "x"},
                        "handler": "tests.support.handlers:uppercase_last_message",
                    }
                ],
            }
        )


def test_rejects_node_with_neither_llm_nor_handler() -> None:
    with pytest.raises(ValidationError, match="sets neither 'llm' nor 'handler'"):
        Schema.model_validate({"schema_version": 1, "nodes": [{"id": "chat"}]})


def test_rejects_tools_on_handler_node() -> None:
    with pytest.raises(ValidationError, match="'tools' only applies to LLM-backed nodes"):
        Schema.model_validate(
            {
                "schema_version": 1,
                "nodes": [
                    {
                        "id": "shout",
                        "handler": "tests.support.handlers:uppercase_last_message",
                        "tools": ["tests.support.tools:echo"],
                    }
                ],
            }
        )
