from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner
from langchain_core.messages import AIMessage

from agentdraft.cli import main

FIXTURE = Path(__file__).parent.parent / "fixtures" / "skeleton.yaml"


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


def test_agentdraft_run_fails_on_missing_schema_file() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["run", "does-not-exist.yaml", "hi"])

    assert result.exit_code != 0
