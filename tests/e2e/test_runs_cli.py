from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner
from langchain_core.messages import AIMessage

from agc.cli import main

FIXTURE = Path(__file__).parent.parent / "fixtures" / "skeleton.yaml"
CHECKPOINTED_FIXTURE = Path(__file__).parent.parent / "fixtures" / "checkpointed.yaml"


def test_runs_list_reports_none_recorded() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["runs", "list"])

    assert result.exit_code == 0
    assert "no recorded runs" in result.output


@patch("agc.compiler.init_chat_model")
def test_runs_list_shows_a_completed_run(mock_init_chat_model: MagicMock) -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="hi")
    mock_init_chat_model.return_value = mock_llm

    runner = CliRunner()
    with runner.isolated_filesystem():
        run_result = runner.invoke(main, ["run", str(FIXTURE), "hi"])
        assert run_result.exit_code == 0

        list_result = runner.invoke(main, ["runs", "list"])

    assert list_result.exit_code == 0
    assert "completed" in list_result.output
    assert str(FIXTURE) in list_result.output


@patch("agc.compiler.init_chat_model")
def test_runs_list_filters_by_schema_path(mock_init_chat_model: MagicMock) -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="hi")
    mock_init_chat_model.return_value = mock_llm

    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(main, ["run", str(FIXTURE), "hi"])
        other = Path("other.yaml")
        other.write_text(FIXTURE.read_text())
        runner.invoke(main, ["run", str(other), "hi"])

        filtered = runner.invoke(main, ["runs", "list", str(other)])

    assert filtered.exit_code == 0
    lines = [line for line in filtered.output.splitlines() if line.strip()]
    assert len(lines) == 1
    assert "other.yaml" in lines[0]


@patch("agc.compiler.init_chat_model")
def test_runs_show_prints_full_detail(mock_init_chat_model: MagicMock) -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="hi there")
    mock_init_chat_model.return_value = mock_llm

    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(main, ["run", str(FIXTURE), "hi"])
        list_output = runner.invoke(main, ["runs", "list"]).output
        run_id = list_output.split()[0]

        result = runner.invoke(main, ["runs", "show", run_id])

    assert result.exit_code == 0
    assert f"run_id: {run_id}" in result.output
    assert "status: completed" in result.output
    assert "node timings:" in result.output
    assert "chat: completed" in result.output


@patch("agc.compiler.init_chat_model")
def test_runs_show_includes_thread_id_hint_when_checkpointed(
    mock_init_chat_model: MagicMock,
) -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="hi")
    mock_init_chat_model.return_value = mock_llm

    runner = CliRunner()
    with runner.isolated_filesystem():
        run_output = runner.invoke(main, ["run", str(CHECKPOINTED_FIXTURE), "hi"]).output
        thread_id = run_output.split("thread_id: ")[1].split()[0]
        list_output = runner.invoke(main, ["runs", "list"]).output
        run_id = list_output.split()[0]

        result = runner.invoke(main, ["runs", "show", run_id])

    assert result.exit_code == 0
    assert f"thread_id: {thread_id}" in result.output
    assert f"--resume {thread_id}" in result.output


@patch("agc.compiler.init_chat_model")
def test_runs_show_includes_error_for_a_failed_run(mock_init_chat_model: MagicMock) -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = RuntimeError("boom")
    mock_init_chat_model.return_value = mock_llm

    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(main, ["run", str(FIXTURE), "hi"])
        list_output = runner.invoke(main, ["runs", "list"]).output
        run_id = list_output.split()[0]

        result = runner.invoke(main, ["runs", "show", run_id])

    assert result.exit_code == 0
    assert "status: failed" in result.output
    assert "error: boom" in result.output


def test_runs_show_exits_1_for_unknown_run_id() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["runs", "show", "does-not-exist"])

    assert result.exit_code == 1
    assert "no such run" in result.output


def test_runs_prune_requires_a_filter() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["runs", "prune"])

    assert result.exit_code == 1
    assert "at least one of --older-than or --keep-last" in result.output


def test_runs_prune_rejects_a_malformed_duration() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["runs", "prune", "--older-than", "not-a-duration"])

    assert result.exit_code != 0


@patch("agc.compiler.init_chat_model")
def test_runs_prune_older_than_valid_duration_keeps_recent_runs(
    mock_init_chat_model: MagicMock,
) -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="hi")
    mock_init_chat_model.return_value = mock_llm

    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(main, ["run", str(FIXTURE), "hi"])

        result = runner.invoke(main, ["runs", "prune", "--older-than", "7d"])
        remaining = runner.invoke(main, ["runs", "list"])

    assert result.exit_code == 0
    assert "pruned 0 run(s)" in result.output
    assert "no recorded runs" not in remaining.output


@patch("agc.compiler.init_chat_model")
def test_runs_prune_keep_last_deletes_older_runs(mock_init_chat_model: MagicMock) -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="hi")
    mock_init_chat_model.return_value = mock_llm

    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(main, ["run", str(FIXTURE), "hi"])
        runner.invoke(main, ["run", str(FIXTURE), "hi"])

        result = runner.invoke(main, ["runs", "prune", "--keep-last", "1"])
        remaining = runner.invoke(main, ["runs", "list"])

    assert result.exit_code == 0
    assert "pruned 1 run(s)" in result.output
    assert len([line for line in remaining.output.splitlines() if line.strip()]) == 1
