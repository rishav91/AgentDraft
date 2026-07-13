from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from agentdraft.schema import (
    SUPPORTED_PROVIDERS,
    Checkpointer,
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


def test_parses_conditional_edge_with_max_visits_and_fallback() -> None:
    schema = Schema.model_validate(
        _two_node_schema_dict(
            [
                {
                    "from": "a",
                    "condition": "tests.support.routing:by_last_message_content",
                    "routes": {"positive": "b", "negative": "END"},
                    "max_visits": 3,
                    "fallback": "negative",
                }
            ]
        )
    )

    edge = schema.edges[0]
    assert edge.max_visits == 3
    assert edge.fallback == "negative"


def test_rejects_max_visits_on_a_direct_edge() -> None:
    with pytest.raises(ValidationError, match="sets 'max_visits'/'fallback'"):
        Schema.model_validate(
            _two_node_schema_dict([{"from": "a", "to": "b", "max_visits": 3, "fallback": "x"}])
        )


def test_rejects_max_visits_without_fallback() -> None:
    with pytest.raises(ValidationError, match="without the other"):
        Schema.model_validate(
            _two_node_schema_dict(
                [{"from": "a", "condition": "x:y", "routes": {"k": "b"}, "max_visits": 3}]
            )
        )


def test_rejects_fallback_without_max_visits() -> None:
    with pytest.raises(ValidationError, match="without the other"):
        Schema.model_validate(
            _two_node_schema_dict(
                [{"from": "a", "condition": "x:y", "routes": {"k": "b"}, "fallback": "k"}]
            )
        )


def test_rejects_non_positive_max_visits() -> None:
    with pytest.raises(ValidationError, match="positive integer"):
        Schema.model_validate(
            _two_node_schema_dict(
                [
                    {
                        "from": "a",
                        "condition": "x:y",
                        "routes": {"k": "b"},
                        "max_visits": 0,
                        "fallback": "k",
                    }
                ]
            )
        )


def test_rejects_fallback_not_in_routes() -> None:
    with pytest.raises(ValidationError, match="fallback 'ghost' is not a key"):
        Schema.model_validate(
            _two_node_schema_dict(
                [
                    {
                        "from": "a",
                        "condition": "x:y",
                        "routes": {"k": "b"},
                        "max_visits": 3,
                        "fallback": "ghost",
                    }
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


def test_dump_schema_round_trips_max_visits_and_fallback() -> None:
    schema = Schema.model_validate(
        _two_node_schema_dict(
            [
                {
                    "from": "a",
                    "condition": "tests.support.routing:by_last_message_content",
                    "routes": {"positive": "b", "negative": "END"},
                    "max_visits": 3,
                    "fallback": "negative",
                }
            ]
        )
    )

    dumped = dump_schema(schema)

    assert dumped["edges"][0]["max_visits"] == 3
    assert dumped["edges"][0]["fallback"] == "negative"
    assert Schema.model_validate(yaml.safe_load(schema_to_yaml(schema))) == schema


def test_dump_schema_omits_max_visits_and_fallback_when_unset() -> None:
    schema = Schema.model_validate(
        _two_node_schema_dict(
            [
                {
                    "from": "a",
                    "condition": "tests.support.routing:by_last_message_content",
                    "routes": {"positive": "b", "negative": "END"},
                }
            ]
        )
    )

    dumped = dump_schema(schema)

    assert "max_visits" not in dumped["edges"][0]
    assert "fallback" not in dumped["edges"][0]


def test_save_schema_writes_yaml_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)  # keep the version-history store (FR-9.1) sandboxed
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


def _single_node_dict(checkpointer: dict[str, object] | None = None) -> dict[str, object]:
    data: dict[str, object] = {
        "schema_version": 1,
        "nodes": [{"id": "chat", "llm": {"provider": "anthropic", "model": "claude-sonnet-5"}}],
    }
    if checkpointer is not None:
        data["checkpointer"] = checkpointer
    return data


def test_schema_without_checkpointer_defaults_to_none() -> None:
    schema = Schema.model_validate(_single_node_dict())

    assert schema.checkpointer is None


def test_checkpointer_defaults_to_sqlite_backend() -> None:
    schema = Schema.model_validate(_single_node_dict({}))

    assert schema.checkpointer == Checkpointer(backend="sqlite", dsn_env=None)


def test_checkpointer_postgres_requires_dsn_env() -> None:
    with pytest.raises(ValidationError, match="dsn_env is required when backend is 'postgres'"):
        Schema.model_validate(_single_node_dict({"backend": "postgres"}))


def test_checkpointer_sqlite_rejects_dsn_env() -> None:
    with pytest.raises(ValidationError, match="dsn_env is only valid when backend is 'postgres'"):
        Schema.model_validate(_single_node_dict({"backend": "sqlite", "dsn_env": "SOME_VAR"}))


def test_dump_schema_omits_checkpointer_when_absent() -> None:
    schema = Schema.model_validate(_single_node_dict())

    assert "checkpointer" not in dump_schema(schema)


def test_dump_schema_round_trips_checkpointer_sqlite() -> None:
    schema = Schema.model_validate(_single_node_dict({"backend": "sqlite"}))

    dumped = dump_schema(schema)

    assert dumped["checkpointer"] == {"backend": "sqlite"}
    assert Schema.model_validate(yaml.safe_load(schema_to_yaml(schema))) == schema


def test_dump_schema_round_trips_checkpointer_postgres_dsn_env() -> None:
    schema = Schema.model_validate(_single_node_dict({"backend": "postgres", "dsn_env": "PG_DSN"}))

    dumped = dump_schema(schema)

    assert dumped["checkpointer"] == {"backend": "postgres", "dsn_env": "PG_DSN"}
    assert Schema.model_validate(yaml.safe_load(schema_to_yaml(schema))) == schema
