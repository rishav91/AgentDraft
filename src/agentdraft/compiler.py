"""Compile a validated Schema into a real LangGraph StateGraph.

Phase 1 scope: multiple nodes wired by explicit `edges` (FR-1.1). A schema
with one node and no edges compiles to the Phase 0 straight line
START -> node -> END.
"""

from collections.abc import Callable
from typing import Annotated, TypedDict

from langchain.chat_models import init_chat_model
from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph

from agentdraft.schema import Node, Schema

_SENTINELS = {"START": START, "END": END}


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def _resolve(node_ref: str) -> str:
    return _SENTINELS.get(node_ref, node_ref)


def _make_llm_node(node: Node) -> Callable[[AgentState], AgentState]:
    llm = init_chat_model(node.llm.model, model_provider=node.llm.provider)
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
    for node in schema.nodes:
        graph.add_node(node.id, _make_llm_node(node))

    if not schema.edges:
        # Phase 0 backward-compat: a lone node with no edges runs START -> node -> END.
        only_node = schema.nodes[0]
        graph.add_edge(START, only_node.id)
        graph.add_edge(only_node.id, END)
    else:
        for edge in schema.edges:
            graph.add_edge(_resolve(edge.from_), _resolve(edge.to))

    return graph.compile()
