import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from agc.cli import main

FIXTURE = Path(__file__).parent.parent / "fixtures" / "skeleton.yaml"
COMPREHENSIVE_FIXTURE = Path(__file__).parent.parent / "fixtures" / "comprehensive.yaml"
COMPREHENSIVE_GOLDEN = Path(__file__).parent.parent / "fixtures" / "comprehensive.explain.txt"
COMPREHENSIVE_JSON_GOLDEN = Path(__file__).parent.parent / "fixtures" / "comprehensive.explain.json"
BAD_HANDLER_FIXTURE = Path(__file__).parent.parent / "fixtures" / "unresolvable_handler.yaml"


@patch("agc.compiler.init_chat_model")
def test_agc_explain_prints_structure_without_executing(
    mock_init_chat_model: MagicMock,
) -> None:
    mock_init_chat_model.return_value = MagicMock()

    runner = CliRunner()
    result = runner.invoke(main, ["explain", str(FIXTURE)])

    assert result.exit_code == 0
    assert "nodes:" in result.output
    assert "chat" in result.output
    mock_init_chat_model.return_value.invoke.assert_not_called()


@patch("agc.compiler.init_chat_model")
def test_agc_explain_matches_golden_file(mock_init_chat_model: MagicMock) -> None:
    mock_init_chat_model.return_value = MagicMock()

    runner = CliRunner()
    result = runner.invoke(main, ["explain", str(COMPREHENSIVE_FIXTURE)])

    assert result.exit_code == 0
    assert result.output.strip() == COMPREHENSIVE_GOLDEN.read_text().strip()


@patch("agc.compiler.init_chat_model")
def test_agc_explain_json_matches_golden_file(mock_init_chat_model: MagicMock) -> None:
    mock_init_chat_model.return_value = MagicMock()

    runner = CliRunner()
    result = runner.invoke(main, ["explain", str(COMPREHENSIVE_FIXTURE), "--format", "json"])

    assert result.exit_code == 0
    assert json.loads(result.output) == json.loads(COMPREHENSIVE_JSON_GOLDEN.read_text())


def test_agc_explain_json_exits_2_on_unresolvable_handler() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["explain", str(BAD_HANDLER_FIXTURE), "--format", "json"])

    assert result.exit_code == 2
    assert "could not import module" in result.output
    assert "Traceback" not in result.output


def test_agc_explain_exits_2_on_unresolvable_handler() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["explain", str(BAD_HANDLER_FIXTURE)])

    assert result.exit_code == 2
    assert "could not import module" in result.output
    assert "Traceback" not in result.output
