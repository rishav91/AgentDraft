"""Thin CLI wrapper around the schema/compiler library (FR-2.5): argv
parsing and stdout formatting only, no business logic.

Exit codes (FR-3.4, ARCHITECTURE §4.4): 0 success, 1 validation error,
2 compile error, 3 runtime/execution error.
"""

import hashlib
import json
import re
import traceback
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import click
from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from pydantic import ValidationError

from agentdraft.compiler import CompileError, compile_schema, explain_schema, schema_structure
from agentdraft.evals import EvalsFileError, load_evals_file, run_case
from agentdraft.init import PROVIDER_API_KEY_ENV, ScaffoldExistsError, scaffold
from agentdraft.observability import run_span, shutdown_tracing
from agentdraft.runs import (
    COMPLETED,
    FAILED,
    NodeTiming,
    finish_run,
    get_latest_run_for_thread,
    get_run,
    list_runs,
    now_iso,
    prune_runs,
    start_run,
)
from agentdraft.schema import Schema, format_validation_errors, load_schema
from agentdraft.server import run_canvas_server
from agentdraft.versions import (
    RevisionNotFoundError,
    diff_revisions,
    list_revisions,
    revert_to_revision,
)


def _load_schema_or_exit(schema_path: str) -> Schema:
    """Load SCHEMA_PATH, printing field-specific errors and exiting 1 on failure."""
    try:
        return load_schema(schema_path)
    except ValidationError as exc:
        for msg in format_validation_errors(exc):
            click.echo(f"error: {msg}", err=True)
        raise SystemExit(1) from exc


def _compile_or_exit(schema: Schema) -> CompiledStateGraph:
    """Compile SCHEMA, printing a clean message and exiting 2 on a compile error."""
    try:
        return compile_schema(schema)
    except CompileError as exc:
        click.echo(f"error: {exc}", err=True)
        raise SystemExit(2) from None


@click.group()
def main() -> None:
    """AgentDraft: define agents as YAML, compile them to LangGraph."""
    # Load a `.env` file from cwd if present (e.g. ANTHROPIC_API_KEY/OPENAI_API_KEY) -
    # a real, already-exported env var always wins (override=False), .env is only a
    # fallback. Keys still come from the environment either way (ARCHITECTURE §8);
    # this is just a convenient way to populate it.
    load_dotenv(Path.cwd() / ".env", override=False)


@main.command("init")
@click.argument("dest", type=click.Path(file_okay=False), required=False)
@click.option(
    "--provider",
    type=click.Choice(sorted(PROVIDER_API_KEY_ENV)),
    default="anthropic",
    show_default=True,
    help="Which working template to scaffold.",
)
@click.option("--force", is_flag=True, help="Overwrite files that already exist at DEST.")
def init_cmd(dest: str | None, provider: str, force: bool) -> None:
    """Scaffold a new agent project at DEST (default: current directory)."""
    target = Path(dest) if dest is not None else Path.cwd()
    try:
        written = scaffold(target, provider, force)
    except ScaffoldExistsError as exc:
        click.echo(
            f"error: refusing to overwrite existing file(s): {', '.join(exc.existing)} "
            "(use --force)",
            err=True,
        )
        raise SystemExit(1) from None

    for path in written:
        click.echo(f"created {path}")

    schema_path = target / "schema.yaml"
    click.echo("\nNext steps:")
    click.echo(
        f"  1. cp {target / '.env.example'} {target / '.env'}   "
        f"# then fill in {PROVIDER_API_KEY_ENV[provider]}"
    )
    click.echo(f"  2. agentdraft validate {schema_path}")
    click.echo(f'  3. agentdraft run {schema_path} "<your message>"')


@main.command()
@click.argument("schema_path", type=click.Path(exists=True, dir_okay=False))
def validate(schema_path: str) -> None:
    """Validate SCHEMA_PATH without executing it."""
    _load_schema_or_exit(schema_path)
    click.echo(f"{schema_path}: valid")


@main.command()
@click.argument("schema_path", type=click.Path(exists=True, dir_okay=False))
@click.argument("message", required=False)
@click.option(
    "--resume",
    "thread_id",
    default=None,
    metavar="THREAD_ID",
    help="Resume an interrupted run by its thread_id (FR-5.3) instead of starting a new "
    "one - requires the schema to declare a `checkpointer` block (FR-5.1).",
)
@click.option(
    "--force",
    is_flag=True,
    help="With --resume, skip the check that the schema hasn't changed since thread_id's "
    "last recorded run (FR-5.6) - resume anyway against the current schema.",
)
def run(schema_path: str, message: str | None, thread_id: str | None, force: bool) -> None:
    """Compile SCHEMA_PATH and run it with an initial human MESSAGE.

    MESSAGE is required to start a new run; it's optional with --resume, where
    omitting it just continues the graph from its last checkpoint with no new input.
    """
    is_resume = thread_id is not None
    schema = _load_schema_or_exit(schema_path)
    graph = _compile_or_exit(schema)
    schema_content_hash = hashlib.sha256(Path(schema_path).read_bytes()).hexdigest()

    if is_resume and schema.checkpointer is None:
        click.echo(
            "error: --resume requires the schema to declare a `checkpointer` block (FR-5.5)",
            err=True,
        )
        raise SystemExit(1)
    if message is None and not is_resume:
        click.echo("error: MESSAGE is required to start a new run", err=True)
        raise SystemExit(1)

    config: RunnableConfig | None = None
    if schema.checkpointer is not None:
        if is_resume:
            assert thread_id is not None  # enforced by is_resume's definition
            saver = graph.checkpointer
            assert isinstance(saver, BaseCheckpointSaver)  # schema.checkpointer set => a saver
            if saver.get_tuple({"configurable": {"thread_id": thread_id}}) is None:
                click.echo(f"error: no checkpoint found for thread_id {thread_id!r}", err=True)
                raise SystemExit(1)
            prior = get_latest_run_for_thread(schema_path, thread_id)
            if prior is not None and prior.schema_content_hash != schema_content_hash and not force:
                click.echo(
                    f"error: schema at {schema_path!r} has changed since thread_id "
                    f"{thread_id!r} was last run - resuming would replay this checkpoint "
                    "against a different compiled graph than produced it; use --force to "
                    "resume anyway (FR-5.6)",
                    err=True,
                )
                raise SystemExit(1)
        else:
            thread_id = str(uuid.uuid4())
            click.echo(
                f"thread_id: {thread_id} (resume an interrupted run with: --resume {thread_id})"
            )
        config = {"configurable": {"thread_id": thread_id}}

    input_ = {"messages": [("human", message)]} if message is not None else None

    run_id = start_run(schema_path, schema_content_hash, thread_id)
    node_timings: list[NodeTiming] = []
    boundary = now_iso()

    try:
        with run_span(run_id, schema_path):
            for chunk in graph.stream(input_, config=config):
                for node_name, node_output in chunk.items():
                    ended_at = now_iso()
                    node_timings.append(
                        NodeTiming(
                            node=node_name,
                            started_at=boundary,
                            ended_at=ended_at,
                            status="completed",
                        )
                    )
                    boundary = ended_at
                    for msg in node_output["messages"]:
                        click.echo(f"[{node_name}] {msg.content}")
    except Exception as exc:
        # LangGraph's own runtime error surfaces as-is (ARCHITECTURE §7) - only the
        # exit code is AgentDraft's to control.
        finish_run(run_id, status=FAILED, node_timings=node_timings, error=str(exc), exit_code=3)
        shutdown_tracing()
        traceback.print_exc()
        raise SystemExit(3) from None

    finish_run(run_id, status=COMPLETED, node_timings=node_timings, error=None, exit_code=0)
    shutdown_tracing()


@main.command()
@click.argument("schema_path", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format: human-readable text (default), or machine-readable JSON (FR-3.5), "
    "the data source for the canvas (ADR-007).",
)
def explain(schema_path: str, output_format: str) -> None:
    """Print SCHEMA_PATH's compiled structure, without executing it."""
    schema = _load_schema_or_exit(schema_path)
    try:
        if output_format == "json":
            compile_schema(schema)
            click.echo(json.dumps(schema_structure(schema), indent=2))
        else:
            click.echo(explain_schema(schema))
    except CompileError as exc:
        click.echo(f"error: {exc}", err=True)
        raise SystemExit(2) from None


@main.command("eval")
@click.argument("schema_path", type=click.Path(exists=True, dir_okay=False))
@click.argument("evals_path", type=click.Path(exists=True, dir_okay=False))
def eval_cmd(schema_path: str, evals_path: str) -> None:
    """Run EVALS_PATH's cases against SCHEMA_PATH, asserting on final graph state (FR-8)."""
    try:
        cases = load_evals_file(evals_path)
    except EvalsFileError as exc:
        click.echo(f"error: {exc}", err=True)
        raise SystemExit(1) from None

    schema = _load_schema_or_exit(schema_path)
    graph = _compile_or_exit(schema)

    passed = 0
    failed = 0
    for case in cases:
        try:
            result = run_case(graph, case)
        except Exception:
            traceback.print_exc()
            raise SystemExit(3) from None

        status = "PASS" if result.passed else "FAIL"
        click.echo(f"[{status}] {result.name}")
        for assertion_result in result.assertion_results:
            click.echo(f"    {assertion_result.message}")
        if result.passed:
            passed += 1
        else:
            failed += 1

    click.echo(f"\n{passed} passed, {failed} failed")
    if failed:
        raise SystemExit(4)


@main.group()
def schema() -> None:
    """Local schema version history (FR-9)."""


@schema.command("log")
@click.argument("schema_path", type=click.Path(exists=True, dir_okay=False))
def schema_log(schema_path: str) -> None:
    """List recorded revisions of SCHEMA_PATH, most recent first (FR-9.2)."""
    revisions = list_revisions(schema_path)
    if not revisions:
        click.echo(f"{schema_path}: no recorded revisions")
        return
    for rev in revisions:
        click.echo(f"revision {rev.revision}  {rev.created_at}  {rev.content_hash[:12]}")


@schema.command("diff")
@click.argument("schema_path", type=click.Path(exists=True, dir_okay=False))
@click.argument("revision_a", type=int)
@click.argument("revision_b", type=int)
def schema_diff(schema_path: str, revision_a: int, revision_b: int) -> None:
    """Show a unified diff between REVISION_A and REVISION_B of SCHEMA_PATH (FR-9.3)."""
    try:
        click.echo(diff_revisions(schema_path, revision_a, revision_b), nl=False)
    except RevisionNotFoundError as exc:
        click.echo(f"error: {exc}", err=True)
        raise SystemExit(1) from None


@schema.command("revert")
@click.argument("schema_path", type=click.Path(exists=True, dir_okay=False))
@click.argument("revision", type=int)
def schema_revert(schema_path: str, revision: int) -> None:
    """Restore SCHEMA_PATH to REVISION's recorded content as a new revision (FR-9.5)."""
    try:
        result = revert_to_revision(schema_path, revision)
    except RevisionNotFoundError as exc:
        click.echo(f"error: {exc}", err=True)
        raise SystemExit(1) from None
    if result.revision == revision:
        click.echo(f"{schema_path}: already at revision {revision}'s content")
    else:
        click.echo(
            f"{schema_path}: reverted to revision {revision}'s content "
            f"as new revision {result.revision}"
        )


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _parse_duration(value: str) -> timedelta:
    """Parse a simple duration like `7d`, `24h`, `30m`, `45s` for `--older-than`."""
    match = re.fullmatch(r"(\d+)([dhms])", value)
    if match is None:
        raise click.BadParameter(
            f"{value!r} - expected a number followed by d/h/m/s, e.g. '7d' or '24h'"
        )
    amount, unit = int(match.group(1)), match.group(2)
    unit_to_kwarg = {"d": "days", "h": "hours", "m": "minutes", "s": "seconds"}
    return timedelta(**{unit_to_kwarg[unit]: amount})


@main.group()
def runs() -> None:
    """Local run history (FR-6)."""


@runs.command("list")
@click.argument("schema_path", type=click.Path(exists=True, dir_okay=False), required=False)
def runs_list(schema_path: str | None) -> None:
    """List recorded runs, most recent first, optionally filtered to one schema (FR-6.2)."""
    records = list_runs(schema_path)
    if not records:
        click.echo("no recorded runs")
        return
    for r in records:
        duration = "-"
        if r.ended_at is not None:
            duration = f"{(_parse_iso(r.ended_at) - _parse_iso(r.started_at)).total_seconds():.1f}s"
        click.echo(f"{r.run_id}  {r.schema_path}  {r.status:<11}  {duration}")


@runs.command("show")
@click.argument("run_id")
def runs_show(run_id: str) -> None:
    """Print full detail for one run: node timings, error, resumability (FR-6.3)."""
    r = get_run(run_id)
    if r is None:
        click.echo(f"error: no such run {run_id!r}", err=True)
        raise SystemExit(1)

    click.echo(f"run_id: {r.run_id}")
    click.echo(f"schema_path: {r.schema_path}")
    click.echo(f"status: {r.status}")
    click.echo(f"started_at: {r.started_at}")
    click.echo(f"ended_at: {r.ended_at or '-'}")
    if r.thread_id is not None:
        click.echo(f"thread_id: {r.thread_id} (resume with: --resume {r.thread_id})")
    if r.error is not None:
        click.echo(f"error: {r.error}")
    click.echo("node timings:")
    if not r.node_timings:
        click.echo("  (none recorded)")
    for t in r.node_timings:
        click.echo(f"  {t.node}: {t.status} ({t.started_at} -> {t.ended_at})")


@runs.command("prune")
@click.option(
    "--older-than",
    "older_than_str",
    default=None,
    metavar="DURATION",
    help="Delete eligible runs older than this (e.g. '7d', '24h'). "
    "At least one of --older-than/--keep-last is required (FR-6.4).",
)
@click.option(
    "--keep-last",
    "keep_last",
    type=int,
    default=None,
    metavar="N",
    help="Always keep the N most recent runs regardless of age.",
)
def runs_prune(older_than_str: str | None, keep_last: int | None) -> None:
    """Delete run-ledger entries on explicit request only - never a run still in flight."""
    if older_than_str is None and keep_last is None:
        click.echo("error: at least one of --older-than or --keep-last is required", err=True)
        raise SystemExit(1)
    older_than = _parse_duration(older_than_str) if older_than_str is not None else None
    count = prune_runs(older_than=older_than, keep_last=keep_last)
    click.echo(f"pruned {count} run(s)")


@main.command()
@click.argument("schema_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--port", type=int, default=0, help="Port to bind (default: an OS-picked free port).")
@click.option(
    "--scan-dir",
    "scan_dirs",
    multiple=True,
    type=click.Path(),
    help="Restrict handler/condition/tool suggestions (FR-4.5) to this directory "
    "(relative to cwd); repeatable. Default: scan the whole current directory.",
)
def canvas(schema_path: str, port: int, scan_dirs: tuple[str, ...]) -> None:
    """Start the local editing API for SCHEMA_PATH, for the canvas frontend (FR-4.3)."""
    _load_schema_or_exit(schema_path)  # fail fast on an already-invalid schema
    run_canvas_server(  # pragma: no cover - see test_server.py
        Path(schema_path), port=port, scan_dirs=[Path(d) for d in scan_dirs]
    )


if __name__ == "__main__":
    main()
