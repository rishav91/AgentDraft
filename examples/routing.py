"""Real, importable conditional-edge routing function for
examples/openai_docs_qa.yaml.
"""

from typing import Any


def by_router_verdict(state: dict[str, Any]) -> str:
    """Read the router node's one-word verdict ("docs" or "chat")."""
    verdict = state["messages"][-1].content.strip().lower()
    return "docs" if "docs" in verdict else "chat"
