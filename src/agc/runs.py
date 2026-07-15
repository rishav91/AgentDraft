"""Local run ledger (`FR-6`, `ADR-010`): one row per `agc run` invocation
that reaches actual graph execution, in the shared `.agc/state.db` file
also used by checkpointing (`ADR-009`) and schema version history (`FR-9`).
Complements observability ([OBSERVABILITY.md](../../docs/OBSERVABILITY.md)) as the
always-on, zero-config local record of a run - useful even with no external
tracing backend configured.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from agc.store import ensure_local_store_dir

RUNNING = "running"
COMPLETED = "completed"
FAILED = "failed"
INTERRUPTED = "interrupted"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    schema_path TEXT NOT NULL,
    schema_content_hash TEXT NOT NULL,
    thread_id TEXT,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    node_timings TEXT NOT NULL DEFAULT '[]',
    error TEXT,
    exit_code INTEGER,
    pid INTEGER NOT NULL
)
"""
_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_runs_schema_path_started_at ON runs (schema_path, started_at)
"""
_COLUMNS = (
    "run_id, schema_path, schema_content_hash, thread_id, status, "
    "started_at, ended_at, node_timings, error, exit_code, pid"
)


@dataclass(frozen=True)
class NodeTiming:
    node: str
    started_at: str
    ended_at: str
    status: str


@dataclass(frozen=True)
class Run:
    run_id: str
    schema_path: str
    schema_content_hash: str
    thread_id: str | None
    status: str
    started_at: str
    ended_at: str | None
    node_timings: list[NodeTiming]
    error: str | None
    exit_code: int | None


def _connect() -> sqlite3.Connection:
    db_path = ensure_local_store_dir()
    conn = sqlite3.connect(str(db_path))
    conn.execute(_CREATE_TABLE)
    conn.execute(_CREATE_INDEX)
    return conn


def _normalize_path(schema_path: str | Path) -> str:
    path = Path(schema_path)
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _process_alive(pid: int) -> bool:
    """Best-effort liveness check backing the `running` -> `interrupted` read-time
    reconciliation (`NFR-7.1`, `DATA-MODEL.md` §4). POSIX-only; any ambiguous result
    (permission error, unsupported platform) is treated as "alive" so a genuinely
    in-flight run is never mislabeled.
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def _row_to_run(row: tuple[Any, ...]) -> Run:
    (
        run_id,
        schema_path,
        schema_content_hash,
        thread_id,
        status,
        started_at,
        ended_at,
        node_timings_json,
        error,
        exit_code,
        pid,
    ) = row
    if status == RUNNING and not _process_alive(pid):
        status = INTERRUPTED
    node_timings = [NodeTiming(**entry) for entry in json.loads(node_timings_json)]
    return Run(
        run_id=run_id,
        schema_path=schema_path,
        schema_content_hash=schema_content_hash,
        thread_id=thread_id,
        status=status,
        started_at=started_at,
        ended_at=ended_at,
        node_timings=node_timings,
        error=error,
        exit_code=exit_code,
    )


def start_run(schema_path: str | Path, schema_content_hash: str, thread_id: str | None) -> str:
    """Record the start of a new run (`FR-6.1`). Returns the new `run_id`."""
    run_id = str(uuid.uuid4())
    with _connect() as conn:
        conn.execute(
            "INSERT INTO runs (run_id, schema_path, schema_content_hash, thread_id, status, "
            "started_at, node_timings, pid) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                _normalize_path(schema_path),
                schema_content_hash,
                thread_id,
                RUNNING,
                now_iso(),
                "[]",
                os.getpid(),
            ),
        )
    return run_id


def finish_run(
    run_id: str,
    *,
    status: str,
    node_timings: list[NodeTiming],
    error: str | None,
    exit_code: int | None,
) -> None:
    """Record the end of a run, success or failure (`FR-6.1`)."""
    with _connect() as conn:
        conn.execute(
            "UPDATE runs SET status = ?, ended_at = ?, node_timings = ?, error = ?, "
            "exit_code = ? WHERE run_id = ?",
            (
                status,
                now_iso(),
                json.dumps([t.__dict__ for t in node_timings]),
                error,
                exit_code,
                run_id,
            ),
        )


def list_runs(schema_path: str | Path | None = None) -> list[Run]:
    """List recorded runs, most recent first (`FR-6.2`), optionally filtered to
    one schema path.
    """
    with _connect() as conn:
        if schema_path is not None:
            rows = conn.execute(
                f"SELECT {_COLUMNS} FROM runs WHERE schema_path = ? ORDER BY started_at DESC",
                (_normalize_path(schema_path),),
            ).fetchall()
        else:
            rows = conn.execute(f"SELECT {_COLUMNS} FROM runs ORDER BY started_at DESC").fetchall()
    return [_row_to_run(row) for row in rows]


def get_run(run_id: str) -> Run | None:
    """Fetch one recorded run by id (`FR-6.3`), or `None` if it doesn't exist."""
    with _connect() as conn:
        row = conn.execute(f"SELECT {_COLUMNS} FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    return _row_to_run(row) if row is not None else None


def get_latest_run_for_thread(schema_path: str | Path, thread_id: str) -> Run | None:
    """Fetch the most recent recorded run for THREAD_ID on SCHEMA_PATH - the
    baseline `--resume`'s schema-consistency guard checks against (`FR-5.6`).
    `None` if no run is recorded (guard has nothing to check against).
    """
    with _connect() as conn:
        row = conn.execute(
            f"SELECT {_COLUMNS} FROM runs WHERE schema_path = ? AND thread_id = ? "
            "ORDER BY started_at DESC LIMIT 1",
            (_normalize_path(schema_path), thread_id),
        ).fetchone()
    return _row_to_run(row) if row is not None else None


def prune_runs(*, older_than: timedelta | None = None, keep_last: int | None = None) -> int:
    """Delete run-ledger rows (`FR-6.4`) - never a row that's still genuinely
    in-flight (status `running` with a live process). Among the rest, KEEP_LAST
    protects the N most recent regardless of age, and OLDER_THAN additionally
    restricts deletion to rows older than that. Returns the number of rows deleted.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT run_id, status, started_at, pid FROM runs ORDER BY started_at DESC"
        ).fetchall()

        cutoff = datetime.now(UTC) - older_than if older_than is not None else None
        to_delete: list[str] = []
        for rank, (run_id, status, started_at, pid) in enumerate(rows):
            if status == RUNNING and _process_alive(int(pid)):
                continue
            if keep_last is not None and rank < keep_last:
                continue
            if cutoff is not None and datetime.fromisoformat(started_at) >= cutoff:
                continue
            to_delete.append(run_id)

        if to_delete:
            conn.executemany("DELETE FROM runs WHERE run_id = ?", [(r,) for r in to_delete])
    return len(to_delete)
