from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner
from langchain_core.messages import AIMessage

from agentdraft.cli import main

FIXTURES = Path(__file__).parent.parent / "fixtures"
SCHEMA_FIXTURE = FIXTURES / "skeleton.yaml"
BAD_PROVIDER_FIXTURE = FIXTURES / "invalid_provider.yaml"
BAD_HANDLER_FIXTURE = FIXTURES / "unresolvable_handler.yaml"
EVALS_ALL_PASS = FIXTURES / "evals_all_pass.yaml"
EVALS_BASIC = FIXTURES / "evals_basic.yaml"
EVALS_MISSING_SCHEMA = FIXTURES / "evals_missing_schema.yaml"
EVALS_BAD_SCHEMA_PATH = FIXTURES / "evals_bad_schema_path.yaml"
EVALS_MISSING_CASES = FIXTURES / "evals_missing_cases.yaml"


@patch("agentdraft.compiler.init_chat_model")
def test_eval_all_cases_pass_exits_0(mock_init_chat_model: MagicMock) -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="Hello, world!")
    mock_init_chat_model.return_value = mock_llm

    runner = CliRunner()
    result = runner.invoke(main, ["eval", str(SCHEMA_FIXTURE), str(EVALS_ALL_PASS)])

    assert result.exit_code == 0
    assert "2 passed, 0 failed" in result.output
    assert "[FAIL]" not in result.output


@patch("agentdraft.compiler.init_chat_model")
def test_eval_a_failing_assertion_exits_4(mock_init_chat_model: MagicMock) -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="Hello, world!")
    mock_init_chat_model.return_value = mock_llm

    runner = CliRunner()
    result = runner.invoke(main, ["eval", str(SCHEMA_FIXTURE), str(EVALS_BASIC)])

    assert result.exit_code == 4
    assert "3 passed, 1 failed" in result.output
    assert "[PASS] equals assertion passes" in result.output
    assert "[FAIL] equals assertion fails" in result.output


@patch("agentdraft.compiler.init_chat_model")
def test_eval_malformed_evals_file_exits_1_before_schema_loads(
    mock_init_chat_model: MagicMock,
) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["eval", str(SCHEMA_FIXTURE), str(EVALS_MISSING_SCHEMA)])

    assert result.exit_code == 1
    assert "'schema' is required" in result.output
    mock_init_chat_model.assert_not_called()


def test_eval_unresolvable_schema_path_in_evals_file_exits_1() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["eval", str(SCHEMA_FIXTURE), str(EVALS_BAD_SCHEMA_PATH)])

    assert result.exit_code == 1
    assert "does not resolve to a file" in result.output


def test_eval_missing_cases_exits_1() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["eval", str(SCHEMA_FIXTURE), str(EVALS_MISSING_CASES)])

    assert result.exit_code == 1
    assert "'cases' is required" in result.output


def test_eval_exits_1_on_invalid_schema() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["eval", str(BAD_PROVIDER_FIXTURE), str(EVALS_ALL_PASS)])

    assert result.exit_code == 1
    assert "Traceback" not in result.output


def test_eval_exits_2_on_compile_error() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["eval", str(BAD_HANDLER_FIXTURE), str(EVALS_ALL_PASS)])

    assert result.exit_code == 2
    assert "could not import module" in result.output
    assert "Traceback" not in result.output


@patch("agentdraft.compiler.init_chat_model")
def test_eval_exits_3_on_runtime_error(mock_init_chat_model: MagicMock) -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = RuntimeError("the LLM provider blew up")
    mock_init_chat_model.return_value = mock_llm

    runner = CliRunner()
    result = runner.invoke(main, ["eval", str(SCHEMA_FIXTURE), str(EVALS_ALL_PASS)])

    assert result.exit_code == 3
    assert "the LLM provider blew up" in result.output


def test_eval_fails_on_missing_evals_file() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["eval", str(SCHEMA_FIXTURE), "does-not-exist.yaml"])

    assert result.exit_code != 0
