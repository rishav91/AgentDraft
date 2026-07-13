"""Compile a validated Schema into a real LangGraph StateGraph.

Phase 1 scope: multiple nodes wired by explicit `edges` (FR-1.1); per-node tool
bindings compiled to LangGraph's own `ToolNode`/`tools_condition` primitives
(FR-1.4); conditional edges, whose routing function is a custom-code
reference resolved at compile time (FR-1.5, `ADR-004`), optionally capped via
`max_visits`/`fallback` to bound a self-loop (FR-1.12); and custom-code nodes,
whose `handler` reference replaces `llm` as the node's entire LangGraph node
function (FR-1.6, FR-2.2, `ADR-004`). A schema with one node and no edges
compiles to the Phase 0 straight line START -> node -> END.
"""

import os
import sqlite3
from collections import defaultdict
from collections.abc import Callable
from typing import Annotated, Any, TypedDict

from langchain.chat_models import init_chat_model
from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agentdraft.loader import HandlerResolutionError, resolve_reference
from agentdraft.schema import Checkpointer, Edge, Node, Schema
from agentdraft.store import ensure_local_store_dir

_SENTINELS = {"START": START, "END": END}


class CompileError(Exception):
    """Raised when a structurally valid schema fails to compile."""


def _sum_visit_counts(current: dict[str, int], update: dict[str, int]) -> dict[str, int]:
    merged = dict(current)
    for node_id, count in update.items():
        merged[node_id] = merged.get(node_id, 0) + count
    return merged


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    # Per-node execution counts, only populated for nodes whose outgoing conditional
    # edge sets `max_visits` (FR-1.12) - absent from every other schema's state.
    edge_visits: Annotated[dict[str, int], _sum_visit_counts]


def _resolve(node_ref: str) -> str:
    return _SENTINELS.get(node_ref, node_ref)


def _resolve_tools(node: Node) -> list[Any]:
    tools = []
    for ref in node.tools:
        try:
            tool = resolve_reference(ref)
        except HandlerResolutionError as exc:
            raise CompileError(f"nodes[{node.id!r}].tools: {exc}") from exc
        tools.append(tool)
    return tools


def _resolve_handler(ref: str, *, context: str) -> Any:
    try:
        return resolve_reference(ref)
    except HandlerResolutionError as exc:
        raise CompileError(f"{context}: {exc}") from exc


def _make_llm_node(node: Node, llm: Any) -> Callable[[AgentState], dict[str, Any]]:
    assert node.llm is not None  # enforced by Schema validation
    system = node.llm.system

    def run_node(state: AgentState) -> dict[str, Any]:
        messages = state["messages"]
        if system is not None:
            messages = [SystemMessage(content=system), *messages]
        response = llm.invoke(messages)
        return {"messages": [response]}

    return run_node


def _with_visit_tracking(
    node_id: str, fn: Callable[[AgentState], dict[str, Any]]
) -> Callable[[AgentState], dict[str, Any]]:
    """Wrap NODE_ID's node function to also record its own execution count
    (`FR-1.12`), for a conditional edge on this node whose `max_visits` needs it.
    """

    def wrapped(state: AgentState) -> dict[str, Any]:
        result = dict(fn(state))
        result["edge_visits"] = {node_id: 1}
        return result

    return wrapped


def _make_capped_condition(
    node_id: str,
    condition_fn: Callable[[AgentState], str],
    max_visits: int,
    fallback: str,
) -> Callable[[AgentState], str]:
    """Force FALLBACK once NODE_ID has executed MAX_VISITS times, instead of
    evaluating the real CONDITION_FN again (`FR-1.12`) - bounds a self-loop
    (e.g. a reflection/self-correction cycle) without hand-written counting
    logic in the schema author's own condition function.
    """

    def wrapped(state: AgentState) -> str:
        visits = state.get("edge_visits", {}).get(node_id, 0)
        if visits >= max_visits:
            return fallback
        return condition_fn(state)

    return wrapped


def _build_sqlite_checkpointer() -> SqliteSaver:
    db_path = ensure_local_store_dir()
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver


def _build_postgres_checkpointer(checkpointer: Checkpointer) -> BaseCheckpointSaver[str]:
    assert checkpointer.dsn_env is not None  # enforced by Checkpointer validation
    dsn = os.environ.get(checkpointer.dsn_env)
    if not dsn:
        raise CompileError(
            f"checkpointer: environment variable {checkpointer.dsn_env!r} (checkpointer.dsn_env) "
            "is not set - it must hold a Postgres connection string"
        )
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg import Connection
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise CompileError(
            "checkpointer.backend: 'postgres' requires the optional postgres extra - "
            "install with `pip install agentdraft[postgres]`"
        ) from exc
    conn = Connection.connect(dsn, autocommit=True, prepare_threshold=0, row_factory=dict_row)
    saver = PostgresSaver(conn)
    saver.setup()
    return saver


def build_checkpointer(checkpointer: Checkpointer | None) -> BaseCheckpointSaver[str] | None:
    """Construct the LangGraph-native checkpointer a schema's `checkpointer` block asks for
    (`FR-5.1`, `ADR-009`) - AgentDraft builds no checkpoint format of its own.
    """
    if checkpointer is None:
        return None
    if checkpointer.backend == "sqlite":
        return _build_sqlite_checkpointer()
    return _build_postgres_checkpointer(checkpointer)


def compile_schema(schema: Schema) -> CompiledStateGraph:
    """Translate a validated schema into a compiled LangGraph StateGraph."""
    checkpointer = build_checkpointer(schema.checkpointer)
    graph = StateGraph(AgentState)
    tool_node_names: dict[str, str] = {}
    # Nodes whose outgoing conditional edge caps its self-loop (FR-1.12) - only
    # these need their node function wrapped to record its own execution count.
    capped_sources = {edge.from_ for edge in schema.edges if edge.max_visits is not None}

    for node in schema.nodes:
        if node.handler is not None:
            handler_fn = _resolve_handler(node.handler, context=f"nodes[{node.id!r}].handler")
            if node.id in capped_sources:
                handler_fn = _with_visit_tracking(node.id, handler_fn)
            graph.add_node(node.id, handler_fn)
            continue

        tools = _resolve_tools(node)
        assert node.llm is not None  # enforced by Schema validation
        try:
            llm: Any = init_chat_model(node.llm.model, model_provider=node.llm.provider)
        except ImportError as exc:
            raise CompileError(f"nodes[{node.id!r}].llm: {exc}") from exc
        if tools:
            llm = llm.bind_tools(tools)
        llm_node_fn: Callable[[AgentState], dict[str, Any]] = _make_llm_node(node, llm)
        if node.id in capped_sources:
            llm_node_fn = _with_visit_tracking(node.id, llm_node_fn)
        graph.add_node(node.id, llm_node_fn)

        if tools:
            tool_node_name = f"{node.id}__tools"
            graph.add_node(tool_node_name, ToolNode(tools, name=tool_node_name))
            graph.add_edge(tool_node_name, node.id)
            tool_node_names[node.id] = tool_node_name

    if not schema.edges:
        # Phase 0 backward-compat: a lone node with no edges runs START -> node -> END.
        only_node = schema.nodes[0]
        graph.add_edge(START, only_node.id)
        if only_node.id in tool_node_names:
            graph.add_conditional_edges(
                only_node.id, tools_condition, {"tools": tool_node_names[only_node.id], END: END}
            )
        else:
            graph.add_edge(only_node.id, END)
        return graph.compile(checkpointer=checkpointer)

    edges_by_source: dict[str, list[Edge]] = defaultdict(list)
    for edge in schema.edges:
        edges_by_source[edge.from_].append(edge)

    for source, out_edges in edges_by_source.items():
        if source in tool_node_names:
            if len(out_edges) != 1 or out_edges[0].to is None:
                raise CompileError(
                    f"nodes[{source!r}]: a tool-bound node must have exactly one direct "
                    "outgoing edge (taken when the LLM does not call a tool); conditional "
                    "edges are not supported on a tool-bound node"
                )
            target = _resolve(out_edges[0].to)
            graph.add_conditional_edges(
                source, tools_condition, {"tools": tool_node_names[source], END: target}
            )
        elif len(out_edges) == 1 and out_edges[0].condition is not None:
            edge = out_edges[0]
            condition_ref = edge.condition
            assert condition_ref is not None  # enforced by Schema validation
            condition_fn = _resolve_handler(condition_ref, context=f"edges[{source!r}].condition")
            if edge.max_visits is not None:
                assert edge.fallback is not None  # enforced by Schema validation
                condition_fn = _make_capped_condition(
                    source, condition_fn, edge.max_visits, edge.fallback
                )
            graph.add_conditional_edges(
                source,
                condition_fn,
                {key: _resolve(target) for key, target in (edge.routes or {}).items()},
            )
        else:
            for edge in out_edges:
                assert edge.to is not None  # enforced by Schema validation
                graph.add_edge(_resolve(source), _resolve(edge.to))

    return graph.compile(checkpointer=checkpointer)


def schema_structure(schema: Schema) -> dict[str, Any]:
    """Structured representation of a schema's compiled graph (FR-3.5).

    Single source of truth for both `explain_schema`'s text rendering and the
    `explain --format json` export the canvas consumes (`ADR-007`) - both read
    this same structure, so they cannot diverge (ROADMAP Phase 2.1 exit
    criterion). Does not itself compile the schema; callers that need
    compile-time errors surfaced should call `compile_schema` first.
    """
    nodes: list[dict[str, Any]] = []
    for node in schema.nodes:
        if node.handler is not None:
            nodes.append(
                {
                    "id": node.id,
                    "kind": "handler",
                    "llm": None,
                    "handler": node.handler,
                    "tools": [],
                }
            )
        else:
            assert node.llm is not None  # enforced by Schema validation
            nodes.append(
                {
                    "id": node.id,
                    "kind": "llm",
                    "llm": {
                        "provider": node.llm.provider,
                        "model": node.llm.model,
                        "system": node.llm.system,
                    },
                    "handler": None,
                    "tools": list(node.tools),
                }
            )

    edges: list[dict[str, Any]] = []
    def _direct(source: str, target: str) -> dict[str, Any]:
        return {
            "from": source,
            "kind": "direct",
            "to": target,
            "condition": None,
            "routes": None,
            "max_visits": None,
            "fallback": None,
        }

    if not schema.edges:
        only_node = schema.nodes[0]
        edges.append(_direct("START", only_node.id))
        edges.append(_direct(only_node.id, "END"))
    else:
        for edge in schema.edges:
            if edge.condition is not None:
                edges.append(
                    {
                        "from": edge.from_,
                        "kind": "conditional",
                        "to": None,
                        "condition": edge.condition,
                        "routes": dict(edge.routes or {}),
                        "max_visits": edge.max_visits,
                        "fallback": edge.fallback,
                    }
                )
            else:
                assert edge.to is not None  # enforced by Schema validation
                edges.append(_direct(edge.from_, edge.to))

    return {"schema_version": schema.schema_version, "nodes": nodes, "edges": edges}


def schema_from_structure(data: dict[str, Any]) -> Schema:
    """Parse a structure dict back into a validated Schema (FR-4.2).

    The inverse of `schema_structure` - same shape `explain --format json` emits and
    the canvas edits. Every field `schema_structure` adds beyond `Schema`'s own shape
    (the `kind` tags, always-present `llm`/`handler`/`tools`/`condition`/`routes` keys)
    is either an ignored extra field or matches that field's own default, so
    `Schema.model_validate` - the same entry point `load_schema` uses - parses it
    directly with no separate reconstruction logic to keep in sync. Raises
    `pydantic.ValidationError` on anything invalid, exactly like `load_schema` does,
    so canvas save errors (`FR-4.4`) get the same field-specific treatment as CLI
    errors (`NFR-2.1`).
    """
    return Schema.model_validate(data)


def explain_schema(schema: Schema) -> str:
    """Render a schema's compiled structure as text, without executing it (FR-3.3).

    Compiles the schema first, purely to surface the same compile-time errors
    `run` would hit (unresolvable tool/handler references) - no LLM or tool
    call happens either way, since compiling only constructs client objects.
    """
    compile_schema(schema)
    structure = schema_structure(schema)

    lines = [f"schema_version: {structure['schema_version']}", "", "nodes:"]
    for node in structure["nodes"]:
        if node["kind"] == "handler":
            lines.append(f"  - {node['id']} (handler: {node['handler']})")
        else:
            llm = node["llm"]
            lines.append(f"  - {node['id']} (llm: {llm['provider']}/{llm['model']})")
            if node["tools"]:
                lines.append(f"      tools: {', '.join(node['tools'])}")

    lines.append("")
    lines.append("edges:")
    for edge in structure["edges"]:
        if edge["kind"] == "conditional":
            routes = ", ".join(f"{key} -> {target}" for key, target in edge["routes"].items())
            line = f"  - {edge['from']} -[{edge['condition']}]-> {{{routes}}}"
            if edge["max_visits"] is not None:
                line += f" (max_visits: {edge['max_visits']}, fallback: {edge['fallback']})"
            lines.append(line)
        else:
            lines.append(f"  - {edge['from']} -> {edge['to']}")

    return "\n".join(lines)
