from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner
from langchain_core.messages import AIMessage

from agentdraft.cli import main

FIXTURE = Path(__file__).parent.parent / "fixtures" / "skeleton.yaml"
TOOL_FIXTURE = Path(__file__).parent.parent / "fixtures" / "tool_calling.yaml"
BAD_HANDLER_FIXTURE = Path(__file__).parent.parent / "fixtures" / "unresolvable_handler.yaml"
BAD_PROVIDER_FIXTURE = Path(__file__).parent.parent / "fixtures" / "invalid_provider.yaml"


@patch("agentdraft.compiler.init_chat_model")
def test_agentdraft_run_end_to_end(mock_init_chat_model: MagicMock) -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="Hello, world!")
    mock_init_chat_model.return_value = mock_llm

    runner = CliRunner()
    result = runner.invoke(main, ["run", str(FIXTURE), "hi"])

    assert result.exit_code == 0
    assert "[chat] Hello, world!" in result.output
    mock_init_chat_model.assert_called_once_with("claude-sonnet-5", model_provider="anthropic")


@patch("agentdraft.compiler.init_chat_model")
def test_agentdraft_run_with_tool_call_end_to_end(mock_init_chat_model: MagicMock) -> None:
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


def test_agentdraft_run_fails_on_missing_schema_file() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["run", "does-not-exist.yaml", "hi"])

    assert result.exit_code != 0


def test_agentdraft_run_exits_1_on_invalid_schema() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["run", str(BAD_PROVIDER_FIXTURE), "hi"])

    assert result.exit_code == 1
    assert "Traceback" not in result.output


def test_agentdraft_run_exits_2_on_compile_error() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["run", str(BAD_HANDLER_FIXTURE), "hi"])

    assert result.exit_code == 2
    assert "could not import module" in result.output
    assert "Traceback" not in result.output


@patch("agentdraft.compiler.init_chat_model")
def test_agentdraft_run_exits_3_on_runtime_error(mock_init_chat_model: MagicMock) -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = RuntimeError("the LLM provider blew up")
    mock_init_chat_model.return_value = mock_llm

    runner = CliRunner()
    result = runner.invoke(main, ["run", str(FIXTURE), "hi"])

    assert result.exit_code == 3
    assert "the LLM provider blew up" in result.output
