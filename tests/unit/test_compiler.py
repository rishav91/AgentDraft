from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agentdraft.compiler import CompileError, compile_schema, schema_structure
from agentdraft.schema import Edge, LLMConfig, Node, Schema


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


def _make_multi_node_schema() -> Schema:
    return Schema(
        schema_version=1,
        nodes=[
            Node(id="a", llm=LLMConfig(provider="anthropic", model="claude-sonnet-5")),
            Node(id="b", llm=LLMConfig(provider="anthropic", model="claude-sonnet-5")),
        ],
        edges=[
            Edge(from_="START", to="a"),
            Edge(from_="a", to="b"),
            Edge(from_="b", to="END"),
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
def test_compile_schema_wires_explicit_edges(mock_init_chat_model: MagicMock) -> None:
    mock_init_chat_model.return_value = MagicMock()
    schema = _make_multi_node_schema()

    graph = compile_schema(schema)

    node_names = set(graph.get_graph().nodes) - {"__start__", "__end__"}
    assert node_names == {"a", "b"}
    edges = {(edge.source, edge.target) for edge in graph.get_graph().edges}
    assert ("__start__", "a") in edges
    assert ("a", "b") in edges
    assert ("b", "__end__") in edges


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


def _make_tool_schema() -> Schema:
    return Schema(
        schema_version=1,
        nodes=[
            Node(
                id="chat",
                llm=LLMConfig(provider="anthropic", model="claude-sonnet-5"),
                tools=["tests.support.tools:echo"],
            )
        ],
    )


@patch("agentdraft.compiler.init_chat_model")
def test_compile_schema_wires_tool_node_and_loop_edge(mock_init_chat_model: MagicMock) -> None:
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_init_chat_model.return_value = mock_llm
    schema = _make_tool_schema()

    graph = compile_schema(schema)

    node_names = set(graph.get_graph().nodes) - {"__start__", "__end__"}
    assert node_names == {"chat", "chat__tools"}
    edges = {(edge.source, edge.target) for edge in graph.get_graph().edges}
    assert ("chat__tools", "chat") in edges
    mock_llm.bind_tools.assert_called_once()
    (bound_tools,), _ = mock_llm.bind_tools.call_args
    assert [t.name for t in bound_tools] == ["echo"]


@patch("agentdraft.compiler.init_chat_model")
def test_run_loops_through_tool_call_then_answers(mock_init_chat_model: MagicMock) -> None:
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.side_effect = [
        AIMessage(
            content="",
            tool_calls=[{"name": "echo", "args": {"text": "hi"}, "id": "call_1"}],
        ),
        AIMessage(content="done"),
    ]
    mock_init_chat_model.return_value = mock_llm
    schema = _make_tool_schema()

    graph = compile_schema(schema)
    result = graph.invoke({"messages": [HumanMessage(content="please echo hi")]})

    assert result["messages"][-1].content == "done"
    tool_messages = [m for m in result["messages"] if m.type == "tool"]
    assert tool_messages[0].content == "hi"
    assert mock_llm.invoke.call_count == 2


@patch("agentdraft.compiler.init_chat_model")
def test_unresolvable_tool_reference_raises_compile_error(mock_init_chat_model: MagicMock) -> None:
    mock_init_chat_model.return_value = MagicMock()
    schema = Schema(
        schema_version=1,
        nodes=[
            Node(
                id="chat",
                llm=LLMConfig(provider="anthropic", model="claude-sonnet-5"),
                tools=["no.such.module:thing"],
            )
        ],
    )

    with pytest.raises(CompileError, match="nodes\\['chat'\\].tools"):
        compile_schema(schema)


def _make_conditional_schema() -> Schema:
    return Schema(
        schema_version=1,
        nodes=[
            Node(id="router", llm=LLMConfig(provider="anthropic", model="claude-sonnet-5")),
            Node(id="yes_path", llm=LLMConfig(provider="anthropic", model="claude-sonnet-5")),
            Node(id="no_path", llm=LLMConfig(provider="anthropic", model="claude-sonnet-5")),
        ],
        edges=[
            Edge(from_="START", to="router"),
            Edge(
                from_="router",
                condition="tests.support.routing:by_last_message_content",
                routes={"positive": "yes_path", "negative": "no_path"},
            ),
            Edge(from_="yes_path", to="END"),
            Edge(from_="no_path", to="END"),
        ],
    )


@patch("agentdraft.compiler.init_chat_model")
def test_compile_schema_wires_conditional_edge(mock_init_chat_model: MagicMock) -> None:
    mock_init_chat_model.return_value = MagicMock()
    schema = _make_conditional_schema()

    graph = compile_schema(schema)

    node_names = set(graph.get_graph().nodes) - {"__start__", "__end__"}
    assert node_names == {"router", "yes_path", "no_path"}


@patch("agentdraft.compiler.init_chat_model")
def test_conditional_edge_routes_to_the_matching_branch(mock_init_chat_model: MagicMock) -> None:
    responses = {
        "router": AIMessage(content="yes, absolutely"),
        "yes_path": AIMessage(content="took the yes branch"),
        "no_path": AIMessage(content="took the no branch"),
    }
    call_order: list[str] = []

    def make_llm(node_name: str) -> MagicMock:
        llm = MagicMock()

        def invoke(messages: list[object]) -> AIMessage:
            call_order.append(node_name)
            return responses[node_name]

        llm.invoke.side_effect = invoke
        return llm

    mock_init_chat_model.side_effect = [
        make_llm("router"),
        make_llm("yes_path"),
        make_llm("no_path"),
    ]
    schema = _make_conditional_schema()

    graph = compile_schema(schema)
    result = graph.invoke({"messages": [HumanMessage(content="well?")]})

    assert call_order == ["router", "yes_path"]
    assert result["messages"][-1].content == "took the yes branch"


@patch("agentdraft.compiler.init_chat_model")
def test_conditional_edge_with_unresolvable_condition_raises_compile_error(
    mock_init_chat_model: MagicMock,
) -> None:
    mock_init_chat_model.return_value = MagicMock()
    schema = Schema(
        schema_version=1,
        nodes=[
            Node(id="router", llm=LLMConfig(provider="anthropic", model="claude-sonnet-5")),
            Node(id="b", llm=LLMConfig(provider="anthropic", model="claude-sonnet-5")),
        ],
        edges=[
            Edge(from_="START", to="router"),
            Edge(from_="router", condition="no.such.module:thing", routes={"k": "b"}),
            Edge(from_="b", to="END"),
        ],
    )

    with pytest.raises(CompileError, match="edges\\['router'\\].condition"):
        compile_schema(schema)


def test_handler_node_runs_the_referenced_callable_directly() -> None:
    schema = Schema(
        schema_version=1,
        nodes=[Node(id="shout", handler="tests.support.handlers:uppercase_last_message")],
    )

    graph = compile_schema(schema)
    result = graph.invoke({"messages": [HumanMessage(content="hello")]})

    assert result["messages"][-1].content == "HELLO"


def test_handler_node_with_unresolvable_handler_raises_compile_error() -> None:
    schema = Schema(
        schema_version=1,
        nodes=[Node(id="shout", handler="no.such.module:thing")],
    )

    with pytest.raises(CompileError, match="nodes\\['shout'\\].handler"):
        compile_schema(schema)


@patch("agentdraft.compiler.init_chat_model")
def test_handler_node_mixed_with_llm_nodes(mock_init_chat_model: MagicMock) -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="hi")
    mock_init_chat_model.return_value = mock_llm
    schema = Schema(
        schema_version=1,
        nodes=[
            Node(id="chat", llm=LLMConfig(provider="anthropic", model="claude-sonnet-5")),
            Node(id="shout", handler="tests.support.handlers:uppercase_last_message"),
        ],
        edges=[
            Edge(from_="START", to="chat"),
            Edge(from_="chat", to="shout"),
            Edge(from_="shout", to="END"),
        ],
    )

    graph = compile_schema(schema)
    result = graph.invoke({"messages": [HumanMessage(content="hello")]})

    assert result["messages"][-1].content == "HI"


@patch("agentdraft.compiler.init_chat_model")
def test_missing_provider_package_raises_compile_error(mock_init_chat_model: MagicMock) -> None:
    mock_init_chat_model.side_effect = ImportError("Unable to import langchain_anthropic")
    schema = _make_schema()

    with pytest.raises(CompileError, match="nodes\\['chat'\\].llm.*langchain_anthropic"):
        compile_schema(schema)


@patch("agentdraft.compiler.init_chat_model")
def test_tool_bound_node_with_conditional_edge_raises_compile_error(
    mock_init_chat_model: MagicMock,
) -> None:
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_init_chat_model.return_value = mock_llm
    schema = Schema(
        schema_version=1,
        nodes=[
            Node(
                id="chat",
                llm=LLMConfig(provider="anthropic", model="claude-sonnet-5"),
                tools=["tests.support.tools:echo"],
            ),
            Node(id="b", llm=LLMConfig(provider="anthropic", model="claude-sonnet-5")),
            Node(id="c", llm=LLMConfig(provider="anthropic", model="claude-sonnet-5")),
        ],
        edges=[
            Edge(from_="START", to="chat"),
            Edge(
                from_="chat",
                condition="tests.support.routing:by_last_message_content",
                routes={"positive": "b", "negative": "c"},
            ),
            Edge(from_="b", to="END"),
            Edge(from_="c", to="END"),
        ],
    )

    with pytest.raises(CompileError, match="'chat'.*exactly one direct"):
        compile_schema(schema)


def test_schema_structure_synthesizes_start_end_for_implicit_single_node() -> None:
    schema = _make_schema(system="be terse")

    structure = schema_structure(schema)

    assert structure["nodes"] == [
        {
            "id": "chat",
            "kind": "llm",
            "llm": {"provider": "anthropic", "model": "claude-sonnet-5", "system": "be terse"},
            "handler": None,
            "tools": [],
        }
    ]
    assert structure["edges"] == [
        {"from": "START", "kind": "direct", "to": "chat", "condition": None, "routes": None},
        {"from": "chat", "kind": "direct", "to": "END", "condition": None, "routes": None},
    ]


def test_schema_structure_covers_tools_handler_and_conditional_routing() -> None:
    schema = Schema(
        schema_version=1,
        nodes=[
            Node(id="router", llm=LLMConfig(provider="anthropic", model="claude-sonnet-5")),
            Node(
                id="search",
                llm=LLMConfig(provider="anthropic", model="claude-sonnet-5"),
                tools=["tests.support.tools:echo"],
            ),
            Node(id="shout", handler="tests.support.handlers:uppercase_last_message"),
        ],
        edges=[
            Edge(from_="START", to="router"),
            Edge(
                from_="router",
                condition="tests.support.routing:by_last_message_content",
                routes={"positive": "search", "negative": "shout"},
            ),
            Edge(from_="search", to="shout"),
            Edge(from_="shout", to="END"),
        ],
    )

    structure = schema_structure(schema)

    assert structure["schema_version"] == 1
    node_by_id = {node["id"]: node for node in structure["nodes"]}
    assert node_by_id["search"]["tools"] == ["tests.support.tools:echo"]
    assert node_by_id["shout"] == {
        "id": "shout",
        "kind": "handler",
        "llm": None,
        "handler": "tests.support.handlers:uppercase_last_message",
        "tools": [],
    }
    conditional = next(edge for edge in structure["edges"] if edge["kind"] == "conditional")
    assert conditional["from"] == "router"
    assert conditional["condition"] == "tests.support.routing:by_last_message_content"
    assert conditional["routes"] == {"positive": "search", "negative": "shout"}
