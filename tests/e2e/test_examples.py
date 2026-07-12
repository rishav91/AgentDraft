"""Exercises examples/docs_qa.yaml - the real, non-trivial agent used to check
the schema-expressiveness success metric (PRD §6): a single-agent, tool-calling
agent with zero custom-code escape-hatch usage.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner
from langchain_core.messages import AIMessage

from agentdraft.cli import main

EXAMPLE = Path(__file__).parent.parent.parent / "examples" / "docs_qa.yaml"


def test_docs_qa_example_validates() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(EXAMPLE)])

    assert result.exit_code == 0


@patch("agentdraft.compiler.init_chat_model")
def test_docs_qa_example_explains_without_executing(mock_init_chat_model: MagicMock) -> None:
    mock_init_chat_model.return_value = MagicMock()

    runner = CliRunner()
    result = runner.invoke(main, ["explain", str(EXAMPLE)])

    assert result.exit_code == 0
    assert "examples.tools:search_docs" in result.output
    mock_init_chat_model.return_value.invoke.assert_not_called()


@patch("agentdraft.compiler.init_chat_model")
def test_docs_qa_example_answers_using_the_real_search_docs_tool(
    mock_init_chat_model: MagicMock,
) -> None:
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.side_effect = [
        AIMessage(
            content="",
            tool_calls=[{"name": "search_docs", "args": {"query": "Phase 2"}, "id": "call_1"}],
        ),
        AIMessage(content="Phase 2 is the canvas."),
    ]
    mock_init_chat_model.return_value = mock_llm

    runner = CliRunner()
    result = runner.invoke(
        main, ["run", str(EXAMPLE), "What does the roadmap say about Phase 2?"]
    )

    assert result.exit_code == 0
    assert "[assistant] Phase 2 is the canvas." in result.output
    # Proves the real tool ran against the real docs/ directory, not a stub.
    assert "docs/" in result.output
