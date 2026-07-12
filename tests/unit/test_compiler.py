from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from agentdraft.compiler import compile_schema
from agentdraft.schema import LLMConfig, Node, Schema


def _make_schema(system: str | None = "be terse") -> Schema:
    return Schema(
        schema_version=1,
        nodes=[
            Node(
                id="chat",
                llm=LLMConfig(provider="anthropic", model="claude-sonnet-5", system=system),
            )
        ],
    )


@patch("agentdraft.compiler.init_chat_model")
def test_compile_schema_wires_single_node_start_to_end(mock_init_chat_model: MagicMock) -> None:
    mock_init_chat_model.return_value = MagicMock()
    schema = _make_schema()

    graph = compile_schema(schema)

    node_names = set(graph.get_graph().nodes) - {"__start__", "__end__"}
    assert node_names == {"chat"}
    mock_init_chat_model.assert_called_once_with("claude-sonnet-5", model_provider="anthropic")


@patch("agentdraft.compiler.init_chat_model")
def test_run_node_prepends_system_message(mock_init_chat_model: MagicMock) -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="hi there")
    mock_init_chat_model.return_value = mock_llm
    schema = _make_schema(system="be terse")

    graph = compile_schema(schema)
    result = graph.invoke({"messages": [HumanMessage(content="hello")]})

    sent_messages = mock_llm.invoke.call_args.args[0]
    assert sent_messages[0].content == "be terse"
    assert sent_messages[1].content == "hello"
    assert result["messages"][-1].content == "hi there"


@patch("agentdraft.compiler.init_chat_model")
def test_run_node_without_system_message(mock_init_chat_model: MagicMock) -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="ok")
    mock_init_chat_model.return_value = mock_llm
    schema = _make_schema(system=None)

    graph = compile_schema(schema)
    graph.invoke({"messages": [HumanMessage(content="hello")]})

    sent_messages = mock_llm.invoke.call_args.args[0]
    assert len(sent_messages) == 1
    assert sent_messages[0].content == "hello"
