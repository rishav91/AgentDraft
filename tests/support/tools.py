"""Real, importable tool/handler targets for compile-time reference resolution
tests (FR-1.4 tool bindings, FR-1.6 custom-code escape hatch). Referenced from
fixture schemas by module path, exactly as a real user's project would be.
"""

from langchain_core.tools import tool


@tool
def echo(text: str) -> str:
    """Echo the given text back, unchanged."""
    return text
