"""Compile a validated Schema into a real LangGraph StateGraph.

Phase 0 scope: one schema node, one LLM call, no tools, no conditional
routing. The compiled graph is a straight line: START -> node -> END.
"""

from typing import Annotated, TypedDict

from langchain.chat_models import init_chat_model
from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph

from agentdraft.schema import Schema


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def compile_schema(schema: Schema) -> CompiledStateGraph:
    """Translate a validated schema into a compiled LangGraph StateGraph."""
    node = schema.nodes[0]
    llm = init_chat_model(node.llm.model, model_provider=node.llm.provider)
    system = node.llm.system

    def run_node(state: AgentState) -> AgentState:
        messages = state["messages"]
        if system is not None:
            messages = [SystemMessage(content=system), *messages]
        response = llm.invoke(messages)
        return {"messages": [response]}

    graph = StateGraph(AgentState)
    graph.add_node(node.id, run_node)
    graph.add_edge(START, node.id)
    graph.add_edge(node.id, END)
    return graph.compile()
