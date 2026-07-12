"""Schema types and loading for AgentDraft.

Phase 1 scope: multi-node graphs with explicit edges (FR-1.1). A schema with
exactly one node and no `edges` section is still accepted and implicitly
wired START -> node -> END, preserving Phase 0 skeleton schemas.
"""

from pathlib import Path
from typing import Any

import yaml
from langchain.chat_models.base import _SUPPORTED_PROVIDERS
from pydantic import BaseModel, Field, model_validator

SUPPORTED_SCHEMA_VERSION = 1
START = "START"
END = "END"


class LLMConfig(BaseModel):
    provider: str
    model: str
    system: str | None = None


class Node(BaseModel):
    id: str
    llm: LLMConfig
    tools: list[str] = []


class Edge(BaseModel):
    from_: str = Field(alias="from")
    to: str

    model_config = {"populate_by_name": True}


class Schema(BaseModel):
    schema_version: int
    nodes: list[Node]
    edges: list[Edge] = []

    @model_validator(mode="after")
    def _check_version(self) -> "Schema":
        if self.schema_version != SUPPORTED_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version: unsupported value {self.schema_version!r} - this AgentDraft "
                f"build supports schema_version {SUPPORTED_SCHEMA_VERSION}"
            )
        return self

    @model_validator(mode="after")
    def _check_nodes(self) -> "Schema":
        if not self.nodes:
            raise ValueError("nodes: at least one node is required")

        ids = [node.id for node in self.nodes]
        seen: set[str] = set()
        for node_id in ids:
            if node_id in seen:
                raise ValueError(f"nodes: duplicate node id {node_id!r}")
            seen.add(node_id)

        if not self.edges:
            if len(self.nodes) > 1:
                raise ValueError(
                    "edges: required when a schema has more than one node - "
                    "add an `edges` section wiring them together"
                )
            return self

        known = seen | {START, END}
        for edge in self.edges:
            if edge.from_ not in known:
                raise ValueError(f"edges: 'from' references unknown node {edge.from_!r}")
            if edge.to not in known:
                raise ValueError(f"edges: 'to' references unknown node {edge.to!r}")
        return self

    @model_validator(mode="after")
    def _check_providers(self) -> "Schema":
        for node in self.nodes:
            if node.llm.provider not in _SUPPORTED_PROVIDERS:
                supported = ", ".join(sorted(_SUPPORTED_PROVIDERS))
                raise ValueError(
                    f"nodes[{node.id!r}].llm.provider: unrecognized provider "
                    f"{node.llm.provider!r} - supported providers: {supported}"
                )
        return self


def load_schema(path: str | Path) -> Schema:
    """Load and structurally validate a YAML schema file."""
    raw: Any = yaml.safe_load(Path(path).read_text())
    return Schema.model_validate(raw)
