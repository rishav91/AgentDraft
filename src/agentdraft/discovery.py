"""Discover importable `module:function` callables for the canvas's handler,
condition, and tool reference fields (FR-4.5).

Static AST scanning, not import - resolving a reference still goes through
`loader.resolve_reference` (real import), but listing *candidates* for a
dropdown/datalist should not execute arbitrary top-level module code just to
populate a suggestion list.
"""

import ast
from pathlib import Path

_EXCLUDED_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
}


def _module_path(py_file: Path, root: Path) -> str | None:
    parts = list(py_file.relative_to(root).parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
        if not parts:
            return None
    else:
        parts[-1] = parts[-1].removesuffix(".py")
    return ".".join(parts)


def get_callable_source(root: Path, ref: str) -> str | None:
    """Return REF's (`module:function`) exact original source text, or None if
    it can't be found - an unresolvable/malformed ref, not an error, since this
    backs a best-effort preview (`FR-4.5`), not the compiler's real resolution
    path (`loader.resolve_reference`, used at compile/run time).
    """
    module_path, _, function_name = ref.partition(":")
    if not function_name:
        return None

    module_root = root.joinpath(*module_path.split("."))
    for candidate in (module_root.with_suffix(".py"), module_root / "__init__.py"):
        if not candidate.is_file():
            continue
        try:
            source = candidate.read_text()
            tree = ast.parse(source, filename=str(candidate))
        except (SyntaxError, UnicodeDecodeError, OSError):
            return None
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if node.name == function_name:
                return ast.get_source_segment(source, node)
        return None
    return None


def discover_callables(root: Path) -> list[str]:
    """Scan ROOT for module-level function definitions, returning `module:function`
    references sorted for stable output. Skips excluded/hidden directories and
    any file that fails to parse - a syntax error elsewhere in the project
    shouldn't break the canvas's suggestion list.
    """
    results: list[str] = []
    for py_file in root.rglob("*.py"):
        rel_parts = py_file.relative_to(root).parts
        if any(part in _EXCLUDED_DIR_NAMES or part.startswith(".") for part in rel_parts[:-1]):
            continue

        module_path = _module_path(py_file, root)
        if module_path is None:
            continue

        try:
            tree = ast.parse(py_file.read_text(), filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError):
            continue

        for node in tree.body:
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if not node.name.startswith("_"):
                results.append(f"{module_path}:{node.name}")

    return sorted(results)
