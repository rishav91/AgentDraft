"""Real, importable conditional-edge routing functions for tests (FR-1.5)."""

from typing import Any


def by_last_message_content(state: dict[str, Any]) -> str:
    last = state["messages"][-1]
    return "positive" if "yes" in last.content.lower() else "negative"
