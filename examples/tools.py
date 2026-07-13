"""A real tool shared by examples/docs_qa.yaml and examples/openai_docs_qa.yaml:
search AgentDraft's own design docs for lines mentioning a query term.
"""

from pathlib import Path

from langchain_core.tools import tool

_DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"


@tool
def search_docs(query: str) -> str:
    """Search AgentDraft's docs/ directory for lines mentioning `query`, case-insensitively."""
    query_lower = query.lower()
    matches: list[str] = []
    for doc_path in sorted(_DOCS_DIR.rglob("*.md")):
        for line_number, line in enumerate(doc_path.read_text().splitlines(), start=1):
            if query_lower in line.lower():
                relative = doc_path.relative_to(_DOCS_DIR.parent)
                matches.append(f"{relative}:{line_number}: {line.strip()}")
    if not matches:
        return "No matching lines found."
    return "\n".join(matches[:10])
