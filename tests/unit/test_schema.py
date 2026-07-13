from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from agentdraft.schema import (
    SUPPORTED_PROVIDERS,
    Schema,
    dump_schema,
    load_schema,
    save_schema,
    schema_to_yaml,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "skeleton.yaml"
MULTI_NODE_FIXTURE = Path(__file__).parent.parent / "fixtures" / "multi_node.yaml"
COMPREHENSIVE_FIXTURE = Path(__file__).parent.parent / "fixtures" / "comprehensive.yaml"


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


def test_supported_providers_matches_what_validation_accepts() -> None:
    assert "anthropic" in SUPPORTED_PROVIDERS
    assert SUPPORTED_PROVIDERS == sorted(SUPPORTED_PROVIDERS)
    for provider in SUPPORTED_PROVIDERS:
        Schema.model_validate(
            {
                "schema_version": 1,
                "nodes": [{"id": "chat", "llm": {"provider": provider, "model": "x"}}],
            }
        )


def test_schema_to_yaml_round_trips_comprehensive_fixture() -> None:
    schema = load_schema(COMPREHENSIVE_FIXTURE)

    reloaded = Schema.model_validate(yaml.safe_load(schema_to_yaml(schema)))

    assert reloaded == schema


def test_dump_schema_omits_edges_for_implicit_single_node_schema() -> None:
    schema = load_schema(FIXTURE)

    assert "edges" not in dump_schema(schema)


def test_dump_schema_omits_tools_and_system_when_unset() -> None:
    schema = Schema.model_validate(
        {
            "schema_version": 1,
            "nodes": [{"id": "chat", "llm": {"provider": "anthropic", "model": "x"}}],
        }
    )

    dumped = dump_schema(schema)

    assert "tools" not in dumped["nodes"][0]
    assert "system" not in dumped["nodes"][0]["llm"]


def test_dump_schema_omits_tools_for_handler_node() -> None:
    schema = Schema.model_validate(
        {
            "schema_version": 1,
            "nodes": [{"id": "shout", "handler": "tests.support.handlers:uppercase_last_message"}],
        }
    )

    dumped = dump_schema(schema)

    assert dumped["nodes"][0] == {
        "id": "shout",
        "handler": "tests.support.handlers:uppercase_last_message",
    }


def test_save_schema_writes_yaml_file(tmp_path: Path) -> None:
    schema = load_schema(COMPREHENSIVE_FIXTURE)
    out_path = tmp_path / "out.yaml"

    save_schema(schema, out_path)

    assert Schema.model_validate(yaml.safe_load(out_path.read_text())) == schema


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
