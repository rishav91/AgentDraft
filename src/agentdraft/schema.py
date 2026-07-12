"""Schema types and loading for AgentDraft.

Phase 1 scope: multi-node graphs with explicit edges (FR-1.1); a node is
either LLM-backed (`llm`, with optional `tools`, FR-1.4) or custom-code
(`handler`, FR-1.6, `ADR-004`), never both. A schema with exactly one node
and no `edges` section is still accepted and implicitly wired
START -> node -> END, preserving Phase 0 skeleton schemas.
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
    llm: LLMConfig | None = None
    tools: list[str] = []
    handler: str | None = None

    @model_validator(mode="after")
    def _check_shape(self) -> "Node":
        if self.llm is not None and self.handler is not None:
            raise ValueError(
                f"nodes[{self.id!r}]: sets both 'llm' and 'handler' - a node is either "
                "LLM-backed ('llm') or custom-code ('handler'), not both"
            )
        if self.llm is None and self.handler is None:
            raise ValueError(f"nodes[{self.id!r}]: sets neither 'llm' nor 'handler'")
        if self.handler is not None and self.tools:
            raise ValueError(
                f"nodes[{self.id!r}]: 'tools' only applies to LLM-backed nodes, not "
                "a 'handler' node - bind tools inside the handler function instead"
            )
        return self


class Edge(BaseModel):
    from_: str = Field(alias="from")
    to: str | None = None
    condition: str | None = None
    routes: dict[str, str] | None = None

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def _check_shape(self) -> "Edge":
        is_conditional = self.condition is not None or self.routes is not None
        if self.to is not None and is_conditional:
            raise ValueError(
                f"edges: edge from {self.from_!r} sets both 'to' and 'condition'/'routes' - "
                "an edge is either direct ('to') or conditional ('condition' + 'routes'), not both"
            )
        if self.to is None and not is_conditional:
            raise ValueError(
                f"edges: edge from {self.from_!r} sets neither 'to' nor 'condition'/'routes'"
            )
        if is_conditional and (self.condition is None or not self.routes):
            raise ValueError(
                f"edges: conditional edge from {self.from_!r} requires both "
                "'condition' and a non-empty 'routes' mapping"
            )
        return self


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
        by_source: dict[str, list[Edge]] = {}
        for edge in self.edges:
            if edge.from_ not in known:
                raise ValueError(f"edges: 'from' references unknown node {edge.from_!r}")
            if edge.to is not None and edge.to not in known:
                raise ValueError(f"edges: 'to' references unknown node {edge.to!r}")
            if edge.routes is not None:
                for key, target in edge.routes.items():
                    if target not in known:
                        raise ValueError(
                            f"edges: routes[{key!r}] from {edge.from_!r} references "
                            f"unknown node {target!r}"
                        )
            by_source.setdefault(edge.from_, []).append(edge)

        for source, out_edges in by_source.items():
            has_conditional = any(edge.condition is not None for edge in out_edges)
            if has_conditional and len(out_edges) > 1:
                raise ValueError(
                    f"edges: {source!r} has a conditional edge, which must be its only "
                    "outgoing edge"
                )
        return self

    @model_validator(mode="after")
    def _check_providers(self) -> "Schema":
        for node in self.nodes:
            if node.llm is None:
                continue
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
