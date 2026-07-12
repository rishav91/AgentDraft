from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from agentdraft.cli import main

FIXTURE = Path(__file__).parent.parent / "fixtures" / "skeleton.yaml"
COMPREHENSIVE_FIXTURE = Path(__file__).parent.parent / "fixtures" / "comprehensive.yaml"
COMPREHENSIVE_GOLDEN = Path(__file__).parent.parent / "fixtures" / "comprehensive.explain.txt"
BAD_HANDLER_FIXTURE = Path(__file__).parent.parent / "fixtures" / "unresolvable_handler.yaml"


@patch("agentdraft.compiler.init_chat_model")
def test_agentdraft_explain_prints_structure_without_executing(
    mock_init_chat_model: MagicMock,
) -> None:
    mock_init_chat_model.return_value = MagicMock()

    runner = CliRunner()
    result = runner.invoke(main, ["explain", str(FIXTURE)])

    assert result.exit_code == 0
    assert "nodes:" in result.output
    assert "chat" in result.output
    mock_init_chat_model.return_value.invoke.assert_not_called()


@patch("agentdraft.compiler.init_chat_model")
def test_agentdraft_explain_matches_golden_file(mock_init_chat_model: MagicMock) -> None:
    mock_init_chat_model.return_value = MagicMock()

    runner = CliRunner()
    result = runner.invoke(main, ["explain", str(COMPREHENSIVE_FIXTURE)])

    assert result.exit_code == 0
    assert result.output.strip() == COMPREHENSIVE_GOLDEN.read_text().strip()


def test_agentdraft_explain_exits_2_on_unresolvable_handler() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["explain", str(BAD_HANDLER_FIXTURE)])

    assert result.exit_code == 2
    assert "could not import module" in result.output
    assert "Traceback" not in result.output
