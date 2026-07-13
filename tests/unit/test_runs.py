import sqlite3
import subprocess
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from agentdraft.runs import (
    COMPLETED,
    FAILED,
    NodeTiming,
    finish_run,
    get_run,
    list_runs,
    prune_runs,
    start_run,
)
from agentdraft.store import ensure_local_store_dir


def _set_pid(run_id: str, pid: int) -> None:
    """Directly overwrite a run row's stored pid, to exercise the dead-process
    reconciliation path without needing to fake `os.getpid()` for `start_run`.
    """
    db_path = ensure_local_store_dir()
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("UPDATE runs SET pid = ? WHERE run_id = ?", (pid, run_id))


def _dead_pid() -> int:
    proc = subprocess.Popen(["true"])
    proc.wait()
    return proc.pid


def test_start_run_creates_a_running_row() -> None:
    run_id = start_run("schema.yaml", "abc123", None)

    run = get_run(run_id)

    assert run is not None
    assert run.status == "running"
    assert run.schema_path == "schema.yaml"
    assert run.schema_content_hash == "abc123"
    assert run.thread_id is None
    assert run.ended_at is None
    assert run.node_timings == []


def test_start_run_records_thread_id_when_given() -> None:
    run_id = start_run("schema.yaml", "abc123", "thread-1")

    run = get_run(run_id)

    assert run is not None
    assert run.thread_id == "thread-1"


def test_finish_run_marks_completed() -> None:
    run_id = start_run("schema.yaml", "abc123", None)
    timings = [NodeTiming(node="chat", started_at="t0", ended_at="t1", status="completed")]

    finish_run(run_id, status=COMPLETED, node_timings=timings, error=None, exit_code=0)

    run = get_run(run_id)
    assert run is not None
    assert run.status == COMPLETED
    assert run.ended_at is not None
    assert run.exit_code == 0
    assert run.error is None
    assert run.node_timings == timings


def test_finish_run_marks_failed_with_error() -> None:
    run_id = start_run("schema.yaml", "abc123", None)

    finish_run(run_id, status=FAILED, node_timings=[], error="boom", exit_code=3)

    run = get_run(run_id)
    assert run is not None
    assert run.status == FAILED
    assert run.error == "boom"
    assert run.exit_code == 3


def test_get_run_returns_none_for_unknown_id() -> None:
    assert get_run("does-not-exist") is None


def test_list_runs_most_recent_first() -> None:
    first = start_run("schema.yaml", "h1", None)
    finish_run(first, status=COMPLETED, node_timings=[], error=None, exit_code=0)
    second = start_run("schema.yaml", "h2", None)
    finish_run(second, status=COMPLETED, node_timings=[], error=None, exit_code=0)

    run_ids = [r.run_id for r in list_runs("schema.yaml")]

    assert run_ids == [second, first]


def test_list_runs_filters_by_schema_path() -> None:
    a = start_run("a.yaml", "ha", None)
    start_run("b.yaml", "hb", None)

    run_ids = [r.run_id for r in list_runs("a.yaml")]

    assert run_ids == [a]


def test_list_runs_unfiltered_returns_all() -> None:
    a = start_run("a.yaml", "ha", None)
    b = start_run("b.yaml", "hb", None)

    run_ids = {r.run_id for r in list_runs()}

    assert run_ids == {a, b}


def test_list_runs_normalizes_path_outside_cwd(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside_schema.yaml"
    run_id = start_run(outside, "hx", None)

    assert [r.run_id for r in list_runs(outside)] == [run_id]


def test_running_row_with_dead_process_reconciles_to_interrupted() -> None:
    run_id = start_run("schema.yaml", "abc123", None)
    _set_pid(run_id, _dead_pid())

    run = get_run(run_id)

    assert run is not None
    assert run.status == "interrupted"


def test_running_row_with_live_process_stays_running() -> None:
    run_id = start_run("schema.yaml", "abc123", None)

    run = get_run(run_id)

    assert run is not None
    assert run.status == "running"


def test_running_row_treated_as_alive_on_ambiguous_os_error() -> None:
    """A permission error (process exists but isn't ours) or any other OSError
    besides `ProcessLookupError` must never be mislabeled as interrupted.
    """
    run_id = start_run("schema.yaml", "abc123", None)

    with patch("agentdraft.runs.os.kill", side_effect=PermissionError):
        run = get_run(run_id)

    assert run is not None
    assert run.status == "running"


def test_prune_runs_never_deletes_a_live_running_row() -> None:
    run_id = start_run("schema.yaml", "abc123", None)

    deleted = prune_runs(keep_last=0)

    assert deleted == 0
    assert get_run(run_id) is not None


def test_prune_runs_deletes_a_dead_running_row_when_eligible() -> None:
    run_id = start_run("schema.yaml", "abc123", None)
    _set_pid(run_id, _dead_pid())

    deleted = prune_runs(keep_last=0)

    assert deleted == 1
    assert get_run(run_id) is None


def test_prune_runs_keep_last_protects_most_recent() -> None:
    older = start_run("schema.yaml", "h1", None)
    finish_run(older, status=COMPLETED, node_timings=[], error=None, exit_code=0)
    newer = start_run("schema.yaml", "h2", None)
    finish_run(newer, status=COMPLETED, node_timings=[], error=None, exit_code=0)

    deleted = prune_runs(keep_last=1)

    assert deleted == 1
    assert get_run(newer) is not None
    assert get_run(older) is None


def test_prune_runs_older_than_only_deletes_old_rows() -> None:
    run_id = start_run("schema.yaml", "abc123", None)
    finish_run(run_id, status=COMPLETED, node_timings=[], error=None, exit_code=0)

    deleted_none = prune_runs(older_than=timedelta(days=7))
    assert deleted_none == 0
    assert get_run(run_id) is not None

    deleted_all = prune_runs(older_than=timedelta(seconds=-1))
    assert deleted_all == 1
    assert get_run(run_id) is None


def test_prune_runs_combines_keep_last_and_older_than() -> None:
    old = start_run("schema.yaml", "h1", None)
    finish_run(old, status=COMPLETED, node_timings=[], error=None, exit_code=0)
    recent = start_run("schema.yaml", "h2", None)
    finish_run(recent, status=COMPLETED, node_timings=[], error=None, exit_code=0)

    # keep_last=1 protects the most recent regardless of the older_than cutoff
    deleted = prune_runs(older_than=timedelta(seconds=-1), keep_last=1)

    assert deleted == 1
    assert get_run(recent) is not None
    assert get_run(old) is None


def test_prune_runs_no_filters_deletes_everything_not_in_flight() -> None:
    run_id = start_run("schema.yaml", "abc123", None)
    finish_run(run_id, status=COMPLETED, node_timings=[], error=None, exit_code=0)

    deleted = prune_runs()

    assert deleted == 1
    assert get_run(run_id) is None
