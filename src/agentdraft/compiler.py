"""Compile a validated Schema into a real LangGraph StateGraph.

Phase 1 scope: multiple nodes wired by explicit `edges` (FR-1.1); per-node tool
bindings compiled to LangGraph's own `ToolNode`/`tools_condition` primitives
(FR-1.4); conditional edges, whose routing function is a custom-code
reference resolved at compile time (FR-1.5, `ADR-004`); and custom-code nodes,
whose `handler` reference replaces `llm` as the node's entire LangGraph node
function (FR-1.6, FR-2.2, `ADR-004`). A schema with one node and no edges
compiles to the Phase 0 straight line START -> node -> END.
"""

from collections import defaultdict
from collections.abc import Callable
from typing import Annotated, Any, TypedDict

from langchain.chat_models import init_chat_model
from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agentdraft.loader import HandlerResolutionError, resolve_reference
from agentdraft.schema import Edge, Node, Schema

_SENTINELS = {"START": START, "END": END}


class CompileError(Exception):
    """Raised when a structurally valid schema fails to compile."""


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


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


def _make_llm_node(node: Node, llm: Any) -> Callable[[AgentState], AgentState]:
    assert node.llm is not None  # enforced by Schema validation
    system = node.llm.system

    def run_node(state: AgentState) -> AgentState:
        messages = state["messages"]
        if system is not None:
            messages = [SystemMessage(content=system), *messages]
        response = llm.invoke(messages)
        return {"messages": [response]}

    return run_node


def compile_schema(schema: Schema) -> CompiledStateGraph:
    """Translate a validated schema into a compiled LangGraph StateGraph."""
    graph = StateGraph(AgentState)
    tool_node_names: dict[str, str] = {}

    for node in schema.nodes:
        if node.handler is not None:
            handler_fn = _resolve_handler(node.handler, context=f"nodes[{node.id!r}].handler")
            graph.add_node(node.id, handler_fn)
            continue

        tools = _resolve_tools(node)
        assert node.llm is not None  # enforced by Schema validation
        llm: Any = init_chat_model(node.llm.model, model_provider=node.llm.provider)
        if tools:
            llm = llm.bind_tools(tools)
        graph.add_node(node.id, _make_llm_node(node, llm))

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
        return graph.compile()

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
            graph.add_conditional_edges(
                source,
                condition_fn,
                {key: _resolve(target) for key, target in (edge.routes or {}).items()},
            )
        else:
            for edge in out_edges:
                assert edge.to is not None  # enforced by Schema validation
                graph.add_edge(_resolve(source), _resolve(edge.to))

    return graph.compile()


def explain_schema(schema: Schema) -> str:
    """Render a schema's compiled structure as text, without executing it (FR-3.3).

    Compiles the schema first, purely to surface the same compile-time errors
    `run` would hit (unresolvable tool/handler references) - no LLM or tool
    call happens either way, since compiling only constructs client objects.
    """
    compile_schema(schema)

    lines = [f"schema_version: {schema.schema_version}", "", "nodes:"]
    for node in schema.nodes:
        if node.handler is not None:
            lines.append(f"  - {node.id} (handler: {node.handler})")
        else:
            assert node.llm is not None  # enforced by Schema validation
            lines.append(f"  - {node.id} (llm: {node.llm.provider}/{node.llm.model})")
            if node.tools:
                lines.append(f"      tools: {', '.join(node.tools)}")

    lines.append("")
    lines.append("edges:")
    if not schema.edges:
        only_node = schema.nodes[0]
        lines.append(f"  - START -> {only_node.id}")
        lines.append(f"  - {only_node.id} -> END")
    else:
        for edge in schema.edges:
            if edge.condition is not None:
                route_items = (edge.routes or {}).items()
                routes = ", ".join(f"{key} -> {target}" for key, target in route_items)
                lines.append(f"  - {edge.from_} -[{edge.condition}]-> {{{routes}}}")
            else:
                lines.append(f"  - {edge.from_} -> {edge.to}")

    return "\n".join(lines)
