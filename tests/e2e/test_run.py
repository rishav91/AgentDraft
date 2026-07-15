import re
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner
from langchain_core.messages import AIMessage

from agc.cli import main

FIXTURE = Path(__file__).parent.parent / "fixtures" / "skeleton.yaml"
TOOL_FIXTURE = Path(__file__).parent.parent / "fixtures" / "tool_calling.yaml"
BAD_HANDLER_FIXTURE = Path(__file__).parent.parent / "fixtures" / "unresolvable_handler.yaml"
BAD_PROVIDER_FIXTURE = Path(__file__).parent.parent / "fixtures" / "invalid_provider.yaml"
CHECKPOINTED_FIXTURE = Path(__file__).parent.parent / "fixtures" / "checkpointed.yaml"
CHECKPOINTED_MULTI_NODE_FIXTURE = (
    Path(__file__).parent.parent / "fixtures" / "checkpointed_multi_node.yaml"
)


@patch("agc.compiler.init_chat_model")
def test_agc_run_end_to_end(mock_init_chat_model: MagicMock) -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="Hello, world!")
    mock_init_chat_model.return_value = mock_llm

    runner = CliRunner()
    result = runner.invoke(main, ["run", str(FIXTURE), "hi"])

    assert result.exit_code == 0
    assert "[chat] Hello, world!" in result.output
    mock_init_chat_model.assert_called_once_with("claude-sonnet-5", model_provider="anthropic")


@patch("agc.compiler.init_chat_model")
def test_agc_run_with_token_usage_metadata_still_succeeds(
    mock_init_chat_model: MagicMock,
) -> None:
    """FR-7.2: a response exposing usage_metadata is attached to the node's
    OpenTelemetry span, but never changes the run's own visible behavior.
    """
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content="Hello, world!",
        usage_metadata={"input_tokens": 12, "output_tokens": 4, "total_tokens": 16},
    )
    mock_init_chat_model.return_value = mock_llm

    runner = CliRunner()
    result = runner.invoke(main, ["run", str(FIXTURE), "hi"])

    assert result.exit_code == 0
    assert "[chat] Hello, world!" in result.output


@patch("agc.compiler.init_chat_model")
def test_agc_run_with_tool_call_end_to_end(mock_init_chat_model: MagicMock) -> None:
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.side_effect = [
        AIMessage(
            content="",
            tool_calls=[{"name": "echo", "args": {"text": "hi"}, "id": "call_1"}],
        ),
        AIMessage(content="echoed: hi"),
    ]
    mock_init_chat_model.return_value = mock_llm

    runner = CliRunner()
    result = runner.invoke(main, ["run", str(TOOL_FIXTURE), "please echo hi"])

    assert result.exit_code == 0
    assert "[chat] echoed: hi" in result.output


def test_agc_run_fails_on_missing_schema_file() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["run", "does-not-exist.yaml", "hi"])

    assert result.exit_code != 0


def test_agc_run_exits_1_on_invalid_schema() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["run", str(BAD_PROVIDER_FIXTURE), "hi"])

    assert result.exit_code == 1
    assert "Traceback" not in result.output


def test_agc_run_exits_2_on_compile_error() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["run", str(BAD_HANDLER_FIXTURE), "hi"])

    assert result.exit_code == 2
    assert "could not import module" in result.output
    assert "Traceback" not in result.output


@patch("agc.compiler.init_chat_model")
def test_agc_run_exits_3_on_runtime_error(mock_init_chat_model: MagicMock) -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = RuntimeError("the LLM provider blew up")
    mock_init_chat_model.return_value = mock_llm

    runner = CliRunner()
    result = runner.invoke(main, ["run", str(FIXTURE), "hi"])

    assert result.exit_code == 3
    assert "the LLM provider blew up" in result.output


def test_agc_run_without_message_or_resume_exits_1() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["run", str(FIXTURE)])

    assert result.exit_code == 1
    assert "MESSAGE is required" in result.output


def test_agc_run_resume_without_checkpointer_configured_exits_1() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["run", str(FIXTURE), "--resume", "some-thread-id"])

    assert result.exit_code == 1
    assert "requires the schema to declare a `checkpointer` block" in result.output


@patch("agc.compiler.init_chat_model")
def test_agc_run_resume_unknown_thread_id_exits_1(mock_init_chat_model: MagicMock) -> None:
    mock_llm = MagicMock()
    mock_init_chat_model.return_value = mock_llm

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            main, ["run", str(CHECKPOINTED_FIXTURE), "--resume", "never-seen-thread"]
        )

    assert result.exit_code == 1
    assert "no checkpoint found for thread_id" in result.output


@patch("agc.compiler.init_chat_model")
def test_agc_run_with_checkpointer_prints_thread_id(
    mock_init_chat_model: MagicMock,
) -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="reply")
    mock_init_chat_model.return_value = mock_llm

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["run", str(CHECKPOINTED_FIXTURE), "hi"])

    assert result.exit_code == 0
    assert re.search(r"thread_id: \S+", result.output)


@patch("agc.compiler.init_chat_model")
def test_agc_run_resume_continues_from_last_checkpoint_after_a_crash(
    mock_init_chat_model: MagicMock,
) -> None:
    """FR-5.3/NFR-7.1: a run that dies mid-execution can be resumed and continues
    from its last persisted checkpoint - the already-completed node is not re-run.
    """
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [
        AIMessage(content="hello from greeter"),
        RuntimeError("simulated crash in closer"),
    ]
    mock_init_chat_model.return_value = mock_llm

    runner = CliRunner()
    with runner.isolated_filesystem():
        first = runner.invoke(main, ["run", str(CHECKPOINTED_MULTI_NODE_FIXTURE), "hi"])
        assert first.exit_code == 3
        assert "[greeter] hello from greeter" in first.output

        match = re.search(r"thread_id: (\S+)", first.output)
        assert match is not None
        thread_id = match.group(1)

        mock_llm.invoke.side_effect = [AIMessage(content="goodbye from closer")]
        second = runner.invoke(
            main, ["run", str(CHECKPOINTED_MULTI_NODE_FIXTURE), "--resume", thread_id]
        )

    assert second.exit_code == 0
    assert "[greeter]" not in second.output
    assert "[closer] goodbye from closer" in second.output


@patch("agc.compiler.init_chat_model")
def test_agc_run_resume_exits_1_if_schema_changed_since_last_run(
    mock_init_chat_model: MagicMock,
) -> None:
    """FR-5.6: resuming against a schema that changed since the thread's last
    recorded run fails fast rather than silently replaying the checkpoint against a
    different compiled graph.
    """
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [
        AIMessage(content="hello from greeter"),
        RuntimeError("simulated crash in closer"),
    ]
    mock_init_chat_model.return_value = mock_llm

    runner = CliRunner()
    with runner.isolated_filesystem():
        schema_path = Path("schema.yaml")
        schema_path.write_text(CHECKPOINTED_MULTI_NODE_FIXTURE.read_text())

        first = runner.invoke(main, ["run", str(schema_path), "hi"])
        assert first.exit_code == 3

        match = re.search(r"thread_id: (\S+)", first.output)
        assert match is not None
        thread_id = match.group(1)

        schema_path.write_text(schema_path.read_text() + "\n# an unrelated edit\n")

        blocked = runner.invoke(main, ["run", str(schema_path), "--resume", thread_id])
        assert blocked.exit_code == 1
        assert "has changed since thread_id" in blocked.output
        assert mock_llm.invoke.call_count == 2  # the resume never called the LLM again

        mock_llm.invoke.side_effect = [AIMessage(content="goodbye from closer")]
        forced = runner.invoke(main, ["run", str(schema_path), "--resume", thread_id, "--force"])

    assert forced.exit_code == 0
    assert "[closer] goodbye from closer" in forced.output


@patch("agc.compiler.init_chat_model")
def test_agc_run_resume_succeeds_with_no_prior_run_to_compare_against(
    mock_init_chat_model: MagicMock,
) -> None:
    """FR-5.6: the schema-consistency guard is best-effort - if the run ledger has no
    recorded run for this thread_id (e.g. pruned), resume proceeds rather than
    blocking with nothing to compare against.
    """
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [
        AIMessage(content="hello from greeter"),
        RuntimeError("simulated crash in closer"),
    ]
    mock_init_chat_model.return_value = mock_llm

    runner = CliRunner()
    with runner.isolated_filesystem():
        first = runner.invoke(main, ["run", str(CHECKPOINTED_MULTI_NODE_FIXTURE), "hi"])
        assert first.exit_code == 3

        match = re.search(r"thread_id: (\S+)", first.output)
        assert match is not None
        thread_id = match.group(1)

        pruned = runner.invoke(main, ["runs", "prune", "--keep-last", "0"])
        assert pruned.exit_code == 0

        mock_llm.invoke.side_effect = [AIMessage(content="goodbye from closer")]
        second = runner.invoke(
            main, ["run", str(CHECKPOINTED_MULTI_NODE_FIXTURE), "--resume", thread_id]
        )

    assert second.exit_code == 0
    assert "[closer] goodbye from closer" in second.output
