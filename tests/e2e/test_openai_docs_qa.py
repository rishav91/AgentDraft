"""Exercises examples/openai_docs_qa.yaml - the OpenAI-backed companion to
docs_qa.yaml, covering a router node, a tool-calling LLM node, and a
custom-code handler node in one real, runnable graph.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner
from langchain_core.messages import AIMessage

from agentdraft.cli import main

EXAMPLE = Path(__file__).parent.parent.parent / "examples" / "openai_docs_qa.yaml"


def test_openai_docs_qa_example_validates() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(EXAMPLE)])

    assert result.exit_code == 0


@patch("agentdraft.compiler.init_chat_model")
def test_openai_docs_qa_example_explains_without_executing(
    mock_init_chat_model: MagicMock,
) -> None:
    mock_init_chat_model.return_value = MagicMock()

    runner = CliRunner()
    result = runner.invoke(main, ["explain", str(EXAMPLE)])

    assert result.exit_code == 0
    assert "examples.tools:search_docs" in result.output
    assert "examples.handlers:friendly_greeting" in result.output
    assert "examples.routing:by_router_verdict" in result.output
    mock_init_chat_model.return_value.invoke.assert_not_called()


@patch("agentdraft.compiler.init_chat_model")
def test_openai_docs_qa_example_routes_docs_question_through_search_tool(
    mock_init_chat_model: MagicMock,
) -> None:
    mock_router = MagicMock()
    mock_router.invoke.return_value = AIMessage(content="docs")

    mock_search = MagicMock()
    mock_search.bind_tools.return_value = mock_search
    mock_search.invoke.side_effect = [
        AIMessage(
            content="",
            tool_calls=[{"name": "search_docs", "args": {"query": "Phase 2"}, "id": "call_1"}],
        ),
        AIMessage(content="Phase 2 is the canvas."),
    ]
    mock_init_chat_model.side_effect = [mock_router, mock_search]

    runner = CliRunner()
    result = runner.invoke(main, ["run", str(EXAMPLE), "What does the roadmap say about Phase 2?"])

    assert result.exit_code == 0
    assert "[search] Phase 2 is the canvas." in result.output
    # Proves the real tool ran against the real docs/ directory, not a stub.
    assert "docs/" in result.output


@patch("agentdraft.compiler.init_chat_model")
def test_openai_docs_qa_example_routes_small_talk_through_greeting_handler(
    mock_init_chat_model: MagicMock,
) -> None:
    mock_router = MagicMock()
    mock_router.invoke.return_value = AIMessage(content="chat")
    # compile_schema constructs a client for every llm node up front, so the
    # unused `search` node still needs a mock even though this path never
    # reaches it.
    mock_init_chat_model.side_effect = [mock_router, MagicMock()]

    runner = CliRunner()
    result = runner.invoke(main, ["run", str(EXAMPLE), "hello!"])

    assert result.exit_code == 0
    assert "[greet] Hey! Ask me anything about AgentDraft's docs." in result.output
