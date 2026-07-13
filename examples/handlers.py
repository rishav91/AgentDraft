"""Real, importable custom-code node handler for
examples/openai_docs_qa.yaml.
"""

from typing import Any

from langchain_core.messages import AIMessage


def friendly_greeting(state: dict[str, Any]) -> dict[str, Any]:
    """Zero-cost reply for small talk - no docs search or LLM call needed."""
    return {"messages": [AIMessage(content="Hey! Ask me anything about AgentDraft's docs.")]}
