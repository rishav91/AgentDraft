import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from pydantic import ValidationError

from agc.compiler import (
    CompileError,
    build_checkpointer,
    compile_schema,
    explain_schema,
    schema_from_structure,
    schema_structure,
)
from agc.schema import Checkpointer, Edge, LLMConfig, Node, Schema


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


@patch("agc.compiler.init_chat_model")
def test_compile_schema_wires_single_node_start_to_end(mock_init_chat_model: MagicMock) -> None:
    mock_init_chat_model.return_value = MagicMock()
    schema = _make_schema()

    graph = compile_schema(schema)

    node_names = set(graph.get_graph().nodes) - {"__start__", "__end__"}
    assert node_names == {"chat"}
    mock_init_chat_model.assert_called_once_with("claude-sonnet-5", model_provider="anthropic")


@patch("agc.compiler.init_chat_model")
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


@patch("agc.compiler.init_chat_model")
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


@patch("agc.compiler.init_chat_model")
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


@patch("agc.compiler.init_chat_model")
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


@patch("agc.compiler.init_chat_model")
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


@patch("agc.compiler.init_chat_model")
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


@patch("agc.compiler.init_chat_model")
def test_compile_schema_wires_conditional_edge(mock_init_chat_model: MagicMock) -> None:
    mock_init_chat_model.return_value = MagicMock()
    schema = _make_conditional_schema()

    graph = compile_schema(schema)

    node_names = set(graph.get_graph().nodes) - {"__start__", "__end__"}
    assert node_names == {"router", "yes_path", "no_path"}


@patch("agc.compiler.init_chat_model")
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


def _make_capped_reflection_schema(max_visits: int) -> Schema:
    """draft -> critique -> {revise -> draft, good -> END}, capped so an always-
    "revise" critique still terminates after MAX_VISITS executions of critique.
    """
    return Schema(
        schema_version=1,
        nodes=[
            Node(id="draft", llm=LLMConfig(provider="anthropic", model="claude-sonnet-5")),
            Node(id="critique", llm=LLMConfig(provider="anthropic", model="claude-sonnet-5")),
        ],
        edges=[
            Edge(from_="START", to="draft"),
            Edge(from_="draft", to="critique"),
            Edge(
                from_="critique",
                condition="tests.support.routing:by_last_message_content",
                routes={"negative": "draft", "positive": "END"},
                max_visits=max_visits,
                fallback="positive",
            ),
        ],
    )


@patch("agc.compiler.init_chat_model")
def test_max_visits_forces_fallback_after_the_cap_even_though_condition_keeps_looping(
    mock_init_chat_model: MagicMock,
) -> None:
    call_order: list[str] = []

    def make_llm(node_name: str, content: str) -> MagicMock:
        llm = MagicMock()

        def invoke(messages: list[object]) -> AIMessage:
            call_order.append(node_name)
            return AIMessage(content=content)

        llm.invoke.side_effect = invoke
        return llm

    # critique's response never contains "yes", so the real condition function
    # (tests.support.routing:by_last_message_content) would loop back to draft
    # forever without the cap.
    mock_init_chat_model.side_effect = [
        make_llm("draft", "here's a draft"),
        make_llm("critique", "not good enough, try again"),
    ]
    schema = _make_capped_reflection_schema(max_visits=2)

    graph = compile_schema(schema)
    result = graph.invoke({"messages": [HumanMessage(content="write something")]})

    assert call_order == ["draft", "critique", "draft", "critique"]
    assert result["messages"][-1].content == "not good enough, try again"


@patch("agc.compiler.init_chat_model")
def test_max_visits_does_not_interfere_before_the_cap_is_reached(
    mock_init_chat_model: MagicMock,
) -> None:
    responses = iter(["not good enough", "yes, ship it"])
    call_order: list[str] = []

    def make_llm(node_name: str) -> MagicMock:
        llm = MagicMock()

        def invoke(messages: list[object]) -> AIMessage:
            call_order.append(node_name)
            if node_name == "critique":
                return AIMessage(content=next(responses))
            return AIMessage(content="a draft")

        llm.invoke.side_effect = invoke
        return llm

    mock_init_chat_model.side_effect = [make_llm("draft"), make_llm("critique")]
    schema = _make_capped_reflection_schema(max_visits=5)

    graph = compile_schema(schema)
    result = graph.invoke({"messages": [HumanMessage(content="write something")]})

    # The real condition approved on its own (2nd critique) well before the
    # cap of 5 - the fallback never had to kick in.
    assert call_order == ["draft", "critique", "draft", "critique"]
    assert result["messages"][-1].content == "yes, ship it"


@patch("agc.compiler.init_chat_model")
def test_explain_schema_shows_max_visits_and_fallback(mock_init_chat_model: MagicMock) -> None:
    mock_init_chat_model.return_value = MagicMock()
    schema = _make_capped_reflection_schema(max_visits=2)

    text = explain_schema(schema)

    assert (
        "  - critique -[tests.support.routing:by_last_message_content]-> "
        "{negative -> draft, positive -> END} (max_visits: 2, fallback: positive)"
    ) in text


@patch("agc.compiler.init_chat_model")
def test_max_visits_wraps_a_handler_node_too(mock_init_chat_model: MagicMock) -> None:
    schema = Schema(
        schema_version=1,
        nodes=[Node(id="loop_node", handler="tests.support.handlers:uppercase_last_message")],
        edges=[
            Edge(from_="START", to="loop_node"),
            Edge(
                from_="loop_node",
                condition="tests.support.routing:by_last_message_content",
                routes={"negative": "loop_node", "positive": "END"},
                max_visits=2,
                fallback="positive",
            ),
        ],
    )

    graph = compile_schema(schema)
    result = graph.invoke({"messages": [HumanMessage(content="go")]})

    mock_init_chat_model.assert_not_called()  # purely a handler node, no LLM involved
    # Uppercasing "go" is already stable, so without the cap this would loop forever.
    assert result["messages"][-1].content == "GO"
    assert sum(1 for m in result["messages"] if m.content == "GO") == 2


@patch("agc.compiler.init_chat_model")
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


@patch("agc.compiler.init_chat_model")
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


@patch("agc.compiler.init_chat_model")
def test_missing_provider_package_raises_compile_error(mock_init_chat_model: MagicMock) -> None:
    mock_init_chat_model.side_effect = ImportError("Unable to import langchain_anthropic")
    schema = _make_schema()

    with pytest.raises(CompileError, match="nodes\\['chat'\\].llm.*langchain_anthropic"):
        compile_schema(schema)


@patch("agc.compiler.init_chat_model")
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
        {
            "from": "START",
            "kind": "direct",
            "to": "chat",
            "condition": None,
            "routes": None,
            "max_visits": None,
            "fallback": None,
        },
        {
            "from": "chat",
            "kind": "direct",
            "to": "END",
            "condition": None,
            "routes": None,
            "max_visits": None,
            "fallback": None,
        },
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
                max_visits=3,
                fallback="negative",
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
    assert conditional["max_visits"] == 3
    assert conditional["fallback"] == "negative"

    direct = next(edge for edge in structure["edges"] if edge["kind"] == "direct")
    assert direct["max_visits"] is None
    assert direct["fallback"] is None


def test_schema_from_structure_is_the_inverse_of_schema_structure() -> None:
    schema = Schema(
        schema_version=1,
        nodes=[
            Node(id="router", llm=LLMConfig(provider="anthropic", model="claude-sonnet-5")),
            Node(
                id="search",
                llm=LLMConfig(
                    provider="anthropic", model="claude-sonnet-5", system="be terse"
                ),
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
                max_visits=3,
                fallback="negative",
            ),
            Edge(from_="search", to="shout"),
            Edge(from_="shout", to="END"),
        ],
    )

    assert schema_from_structure(schema_structure(schema)) == schema


def test_schema_from_structure_synthesized_start_end_round_trips_to_no_edges() -> None:
    schema = Schema(
        schema_version=1,
        nodes=[Node(id="chat", llm=LLMConfig(provider="anthropic", model="claude-sonnet-5"))],
    )

    rebuilt = schema_from_structure(schema_structure(schema))

    assert rebuilt.nodes == schema.nodes
    assert [(e.from_, e.to) for e in rebuilt.edges] == [("START", "chat"), ("chat", "END")]


def test_schema_from_structure_raises_validation_error_on_invalid_graph() -> None:
    with pytest.raises(ValidationError, match="unrecognized provider"):
        schema_from_structure(
            {
                "schema_version": 1,
                "nodes": [
                    {
                        "id": "chat",
                        "kind": "llm",
                        "llm": {"provider": "not-a-real-provider", "model": "x", "system": None},
                        "handler": None,
                        "tools": [],
                    }
                ],
                "edges": [],
            }
        )


def test_build_checkpointer_returns_none_when_unset() -> None:
    assert build_checkpointer(None) is None


def test_compile_schema_without_checkpointer_has_none() -> None:
    graph = compile_schema(_make_schema())

    assert not graph.checkpointer


def test_compile_schema_with_sqlite_checkpointer_creates_local_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    schema = Schema(
        schema_version=1,
        nodes=[Node(id="chat", llm=LLMConfig(provider="anthropic", model="claude-sonnet-5"))],
        checkpointer=Checkpointer(backend="sqlite"),
    )

    graph = compile_schema(schema)

    assert isinstance(graph.checkpointer, SqliteSaver)
    db_path = tmp_path / ".agc" / "state.db"
    assert db_path.exists()
    tables = {
        row[0]
        for row in sqlite3.connect(db_path).execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert {"checkpoints", "writes"} <= tables


def test_build_checkpointer_postgres_requires_dsn_env_var_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MISSING_PG_DSN", raising=False)
    checkpointer = Checkpointer(backend="postgres", dsn_env="MISSING_PG_DSN")

    with pytest.raises(CompileError, match="MISSING_PG_DSN"):
        build_checkpointer(checkpointer)


def test_build_checkpointer_postgres_missing_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PG_DSN", "postgresql://localhost/test")
    monkeypatch.setitem(sys.modules, "psycopg", None)
    checkpointer = Checkpointer(backend="postgres", dsn_env="PG_DSN")

    with pytest.raises(CompileError, match="requires the optional postgres extra"):
        build_checkpointer(checkpointer)


def test_build_checkpointer_postgres_wires_dsn_and_calls_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PG_DSN", "postgresql://localhost/test")
    checkpointer = Checkpointer(backend="postgres", dsn_env="PG_DSN")

    mock_conn = MagicMock()
    mock_saver = MagicMock()
    with (
        patch("psycopg.Connection.connect", return_value=mock_conn) as mock_connect,
        patch("langgraph.checkpoint.postgres.PostgresSaver", return_value=mock_saver),
    ):
        result = build_checkpointer(checkpointer)

    assert mock_connect.call_args.args == ("postgresql://localhost/test",)
    assert mock_connect.call_args.kwargs["autocommit"] is True
    mock_saver.setup.assert_called_once()
    assert result is mock_saver
