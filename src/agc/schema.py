"""Schema types and loading for Agentic Graph Composer.

Phase 1 scope: multi-node graphs with explicit edges (FR-1.1); a node is
either LLM-backed (`llm`, with optional `tools`, FR-1.4) or custom-code
(`handler`, FR-1.6, `ADR-004`), never both. A schema with exactly one node
and no `edges` section is still accepted and implicitly wired
START -> node -> END, preserving Phase 0 skeleton schemas.
"""

from pathlib import Path
from typing import Any, Literal

import yaml
from langchain.chat_models.base import _SUPPORTED_PROVIDERS
from pydantic import BaseModel, Field, ValidationError, model_validator

from agc.versions import record_revision

# Sorted, public re-export of the same set _check_providers validates against
# (FR-1.3, ADR-005) - the canvas's provider dropdown reads this (FR-4.6) so it
# can never drift from what a save would actually accept.
SUPPORTED_PROVIDERS = sorted(_SUPPORTED_PROVIDERS)

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
    max_visits: int | None = None
    fallback: str | None = None

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
        if self.max_visits is not None or self.fallback is not None:
            if not is_conditional:
                raise ValueError(
                    f"edges: edge from {self.from_!r} sets 'max_visits'/'fallback' - these only "
                    "apply to a conditional edge ('condition' + 'routes')"
                )
            if self.max_visits is None or self.fallback is None:
                raise ValueError(
                    f"edges: conditional edge from {self.from_!r} sets one of "
                    "'max_visits'/'fallback' without the other - both are required together"
                )
            if self.max_visits < 1:
                raise ValueError(
                    f"edges: edge from {self.from_!r}.max_visits must be a positive integer, "
                    f"got {self.max_visits!r}"
                )
            assert self.routes is not None  # enforced by the conditional-edge check above
            if self.fallback not in self.routes:
                raise ValueError(
                    f"edges: edge from {self.from_!r}.fallback {self.fallback!r} is not a key "
                    "in its 'routes' mapping"
                )
        return self


class Checkpointer(BaseModel):
    """Opt-in checkpointing config (`FR-5.1`, `ADR-009`) - a thin passthrough to
    LangGraph's own `SqliteSaver`/`PostgresSaver`, not an Agentic Graph Composer-built abstraction.
    """

    backend: Literal["sqlite", "postgres"] = "sqlite"
    dsn_env: str | None = None

    @model_validator(mode="after")
    def _check_dsn(self) -> "Checkpointer":
        if self.backend == "postgres" and not self.dsn_env:
            raise ValueError(
                "checkpointer.dsn_env is required when backend is 'postgres' - name the "
                "environment variable holding the connection string (never inline it)"
            )
        if self.backend == "sqlite" and self.dsn_env is not None:
            raise ValueError(
                "checkpointer.dsn_env is only valid when backend is 'postgres' - the sqlite "
                "backend uses the shared local store (ADR-010) with no configuration"
            )
        return self


class Schema(BaseModel):
    schema_version: int
    nodes: list[Node]
    edges: list[Edge] = []
    checkpointer: Checkpointer | None = None

    @model_validator(mode="after")
    def _check_version(self) -> "Schema":
        if self.schema_version != SUPPORTED_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version: unsupported value {self.schema_version!r} - this build "
                f"supports schema_version {SUPPORTED_SCHEMA_VERSION}"
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


def format_validation_errors(exc: ValidationError) -> list[str]:
    """Render a ValidationError as the field-specific messages the CLI prints (NFR-2.1).

    Shared by the CLI and the canvas's local save endpoint (FR-4.3, FR-4.4) so both
    surfaces report identical error text for the same invalid schema.
    """
    return [error["msg"].removeprefix("Value error, ") for error in exc.errors()]


def dump_schema(schema: Schema) -> dict[str, Any]:
    """Render a Schema back into a YAML-serializable dict (FR-1.11).

    Inverse of the parsing `load_schema` does. Omits fields the schema doesn't use
    (no `edges:` for an implicit single-node schema, no empty `tools:` on a handler
    node) so a canvas-saved file (`FR-4.3`) still reads like a hand-authored one.
    """
    nodes: list[dict[str, Any]] = []
    for node in schema.nodes:
        entry: dict[str, Any] = {"id": node.id}
        if node.llm is not None:
            llm: dict[str, Any] = {"provider": node.llm.provider, "model": node.llm.model}
            if node.llm.system is not None:
                llm["system"] = node.llm.system
            entry["llm"] = llm
            if node.tools:
                entry["tools"] = list(node.tools)
        else:
            entry["handler"] = node.handler
        nodes.append(entry)

    result: dict[str, Any] = {"schema_version": schema.schema_version, "nodes": nodes}

    if schema.edges:
        edges: list[dict[str, Any]] = []
        for edge in schema.edges:
            edge_entry: dict[str, Any] = {"from": edge.from_}
            if edge.to is not None:
                edge_entry["to"] = edge.to
            else:
                edge_entry["condition"] = edge.condition
                edge_entry["routes"] = dict(edge.routes or {})
                if edge.max_visits is not None:
                    edge_entry["max_visits"] = edge.max_visits
                    edge_entry["fallback"] = edge.fallback
            edges.append(edge_entry)
        result["edges"] = edges

    if schema.checkpointer is not None:
        checkpointer: dict[str, Any] = {"backend": schema.checkpointer.backend}
        if schema.checkpointer.dsn_env is not None:
            checkpointer["dsn_env"] = schema.checkpointer.dsn_env
        result["checkpointer"] = checkpointer

    return result


def schema_to_yaml(schema: Schema) -> str:
    """Serialize a Schema to YAML text (FR-1.11)."""
    return yaml.safe_dump(dump_schema(schema), sort_keys=False, default_flow_style=False)


def save_schema(schema: Schema, path: str | Path) -> None:
    """Write a Schema to PATH as YAML (FR-4.3), recording a new local revision
    unless the content is unchanged from the last recorded one (FR-9.1).
    """
    content = schema_to_yaml(schema)
    Path(path).write_text(content)
    record_revision(path, content)
