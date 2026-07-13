"""Local schema version history (`FR-9`, `ADR-010`): one revision row per distinct
`save_schema` content change, in the shared `.agentdraft/state.db` file also used by
checkpointing (`ADR-009`). Distinct from `schema_version` (`ADR-006`), which is the
schema *format* version a file targets, not an edit-history revision number
(`FR-9.4`).
"""

from __future__ import annotations

import difflib
import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from agentdraft.store import ensure_local_store_dir

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS schema_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schema_path TEXT NOT NULL,
    revision INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""
_CREATE_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_schema_versions_path_revision
    ON schema_versions (schema_path, revision)
"""


class RevisionNotFoundError(Exception):
    """Raised when a requested revision doesn't exist for a schema path (`FR-9.3`)."""

    def __init__(self, schema_path: str | Path, revision: int) -> None:
        super().__init__(f"no revision {revision} recorded for {schema_path}")
        self.schema_path = schema_path
        self.revision = revision


@dataclass(frozen=True)
class SchemaRevision:
    revision: int
    content_hash: str
    content: str
    created_at: str


def _connect() -> sqlite3.Connection:
    db_path = ensure_local_store_dir()
    conn = sqlite3.connect(str(db_path))
    conn.execute(_CREATE_TABLE)
    conn.execute(_CREATE_INDEX)
    return conn


def _normalize_path(schema_path: str | Path) -> str:
    """Store paths relative to cwd when possible, matching the project-relative
    paths the canvas API already reports (`FR-4.7`) - falls back to the raw path
    for a schema outside the current project.
    """
    path = Path(schema_path)
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def record_revision(schema_path: str | Path, content: str) -> SchemaRevision | None:
    """Record CONTENT as a new revision of SCHEMA_PATH, unless it's identical to the
    latest recorded revision (`FR-9.1`). Returns the new revision, or `None` if the
    content was unchanged and no row was inserted.
    """
    key = _normalize_path(schema_path)
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    with _connect() as conn:
        row = conn.execute(
            "SELECT revision, content_hash FROM schema_versions "
            "WHERE schema_path = ? ORDER BY revision DESC LIMIT 1",
            (key,),
        ).fetchone()

        if row is not None and row[1] == content_hash:
            return None

        next_revision = (row[0] + 1) if row is not None else 1
        created_at = datetime.now(UTC).isoformat()
        conn.execute(
            "INSERT INTO schema_versions "
            "(schema_path, revision, content_hash, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (key, next_revision, content_hash, content, created_at),
        )
        return SchemaRevision(next_revision, content_hash, content, created_at)


def list_revisions(schema_path: str | Path) -> list[SchemaRevision]:
    """List recorded revisions for SCHEMA_PATH, most recent first (`FR-9.2`)."""
    key = _normalize_path(schema_path)
    with _connect() as conn:
        rows = conn.execute(
            "SELECT revision, content_hash, content, created_at FROM schema_versions "
            "WHERE schema_path = ? ORDER BY revision DESC",
            (key,),
        ).fetchall()
    return [SchemaRevision(*row) for row in rows]


def get_revision(schema_path: str | Path, revision: int) -> SchemaRevision | None:
    """Fetch one recorded revision of SCHEMA_PATH, or `None` if it doesn't exist."""
    key = _normalize_path(schema_path)
    with _connect() as conn:
        row = conn.execute(
            "SELECT revision, content_hash, content, created_at FROM schema_versions "
            "WHERE schema_path = ? AND revision = ?",
            (key, revision),
        ).fetchone()
    return SchemaRevision(*row) if row is not None else None


def diff_revisions(schema_path: str | Path, revision_a: int, revision_b: int) -> str:
    """Unified diff between two recorded revisions of SCHEMA_PATH (`FR-9.3`)."""
    a = get_revision(schema_path, revision_a)
    if a is None:
        raise RevisionNotFoundError(schema_path, revision_a)
    b = get_revision(schema_path, revision_b)
    if b is None:
        raise RevisionNotFoundError(schema_path, revision_b)

    diff = difflib.unified_diff(
        a.content.splitlines(keepends=True),
        b.content.splitlines(keepends=True),
        fromfile=f"revision {revision_a}",
        tofile=f"revision {revision_b}",
    )
    return "".join(diff)
