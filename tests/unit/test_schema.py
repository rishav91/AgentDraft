from pathlib import Path

import pytest
from pydantic import ValidationError

from agentdraft.schema import Schema, load_schema

FIXTURE = Path(__file__).parent.parent / "fixtures" / "skeleton.yaml"


def test_load_schema_parses_fixture() -> None:
    schema = load_schema(FIXTURE)

    assert schema.schema_version == 1
    assert len(schema.nodes) == 1
    assert schema.nodes[0].id == "chat"
    assert schema.nodes[0].llm.provider == "anthropic"


def test_rejects_unsupported_schema_version() -> None:
    with pytest.raises(ValidationError, match="schema_version"):
        Schema.model_validate(
            {
                "schema_version": 99,
                "nodes": [{"id": "chat", "llm": {"provider": "anthropic", "model": "x"}}],
            }
        )


def test_rejects_more_than_one_node() -> None:
    with pytest.raises(ValidationError, match="exactly one node"):
        Schema.model_validate(
            {
                "schema_version": 1,
                "nodes": [
                    {"id": "a", "llm": {"provider": "anthropic", "model": "x"}},
                    {"id": "b", "llm": {"provider": "anthropic", "model": "x"}},
                ],
            }
        )


def test_rejects_zero_nodes() -> None:
    with pytest.raises(ValidationError, match="exactly one node"):
        Schema.model_validate({"schema_version": 1, "nodes": []})
