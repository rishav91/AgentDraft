"""Real, importable custom-code node handlers for tests (FR-1.6, ADR-004)."""

from typing import Any

from langchain_core.messages import AIMessage


def uppercase_last_message(state: dict[str, Any]) -> dict[str, Any]:
    last = state["messages"][-1]
    return {"messages": [AIMessage(content=last.content.upper())]}
