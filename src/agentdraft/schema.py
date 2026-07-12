"""Schema types and loading for AgentDraft.

Phase 0 scope only: a single node, a single LLM call, no tools, no
branching. The full multi-node/edge/tool schema is Phase 1 (see
docs/ROADMAP.md and docs/requirements/system-requirements.md FR-1.1-FR-1.6).
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, field_validator

SUPPORTED_SCHEMA_VERSION = 1


class LLMConfig(BaseModel):
    provider: str
    model: str
    system: str | None = None


class Node(BaseModel):
    id: str
    llm: LLMConfig


class Schema(BaseModel):
    schema_version: int
    nodes: list[Node]

    @field_validator("schema_version")
    @classmethod
    def _check_version(cls, v: int) -> int:
        if v != SUPPORTED_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported schema_version {v!r}: this AgentDraft build "
                f"supports schema_version {SUPPORTED_SCHEMA_VERSION}"
            )
        return v

    @field_validator("nodes")
    @classmethod
    def _check_single_node(cls, v: list[Node]) -> list[Node]:
        if len(v) != 1:
            raise ValueError(
                "Phase 0 skeleton supports exactly one node "
                f"(got {len(v)}); multi-node graphs land in Phase 1"
            )
        return v


def load_schema(path: str | Path) -> Schema:
    """Load and structurally validate a YAML schema file."""
    raw: Any = yaml.safe_load(Path(path).read_text())
    return Schema.model_validate(raw)
