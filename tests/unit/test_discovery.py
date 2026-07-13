from pathlib import Path

from agentdraft.discovery import discover_callables, get_callable_source


def _write(root: Path, rel_path: str, content: str) -> None:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_discovers_top_level_functions_with_dotted_module_path(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/handlers.py", "def uppercase(state):\n    return state\n")

    assert discover_callables(tmp_path) == ["pkg.handlers:uppercase"]


def test_discovers_async_functions(tmp_path: Path) -> None:
    _write(tmp_path, "mod.py", "async def fetch(state):\n    return state\n")

    assert discover_callables(tmp_path) == ["mod:fetch"]


def test_excludes_private_functions(tmp_path: Path) -> None:
    _write(tmp_path, "mod.py", "def public(): pass\ndef _private(): pass\n")

    assert discover_callables(tmp_path) == ["mod:public"]


def test_excludes_nested_functions(tmp_path: Path) -> None:
    _write(tmp_path, "mod.py", "def outer():\n    def inner():\n        pass\n    return inner\n")

    assert discover_callables(tmp_path) == ["mod:outer"]


def test_init_py_functions_belong_to_the_package_module_path(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/__init__.py", "def route(state):\n    return state\n")

    assert discover_callables(tmp_path) == ["pkg:route"]


def test_skips_excluded_directories(tmp_path: Path) -> None:
    _write(tmp_path, ".venv/lib/thing.py", "def hidden(): pass\n")
    _write(tmp_path, "__pycache__/cached.py", "def hidden2(): pass\n")
    _write(tmp_path, "mod.py", "def visible(): pass\n")

    assert discover_callables(tmp_path) == ["mod:visible"]


def test_skips_files_with_syntax_errors(tmp_path: Path) -> None:
    _write(tmp_path, "broken.py", "def bad(:\n")
    _write(tmp_path, "mod.py", "def visible(): pass\n")

    assert discover_callables(tmp_path) == ["mod:visible"]


def test_root_level_init_py_has_no_module_path_and_is_skipped(tmp_path: Path) -> None:
    _write(tmp_path, "__init__.py", "def route(state):\n    return state\n")

    assert discover_callables(tmp_path) == []


def test_skips_non_function_top_level_statements(tmp_path: Path) -> None:
    _write(tmp_path, "mod.py", "class Thing:\n    pass\n\nX = 1\n\ndef visible(): pass\n")

    assert discover_callables(tmp_path) == ["mod:visible"]


def test_results_are_sorted(tmp_path: Path) -> None:
    _write(tmp_path, "b.py", "def z(): pass\n")
    _write(tmp_path, "a.py", "def y(): pass\n")

    assert discover_callables(tmp_path) == ["a:y", "b:z"]


def test_get_callable_source_returns_exact_original_text(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/handlers.py", "def route(state):\n    # a comment\n    return state\n")

    source = get_callable_source(tmp_path, "pkg.handlers:route")

    assert source == "def route(state):\n    # a comment\n    return state"


def test_get_callable_source_finds_functions_in_package_init(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/__init__.py", "def route(state):\n    return state\n")

    assert get_callable_source(tmp_path, "pkg:route") == "def route(state):\n    return state"


def test_get_callable_source_returns_none_for_malformed_ref(tmp_path: Path) -> None:
    assert get_callable_source(tmp_path, "no-colon-here") is None


def test_get_callable_source_returns_none_for_unknown_module(tmp_path: Path) -> None:
    assert get_callable_source(tmp_path, "does.not.exist:fn") is None


def test_get_callable_source_returns_none_for_unknown_function(tmp_path: Path) -> None:
    _write(tmp_path, "mod.py", "def visible(): pass\n")

    assert get_callable_source(tmp_path, "mod:missing") is None


def test_get_callable_source_skips_non_function_statements_before_the_match(tmp_path: Path) -> None:
    _write(tmp_path, "mod.py", "class Thing:\n    pass\n\ndef route(state):\n    return state\n")

    assert get_callable_source(tmp_path, "mod:route") == "def route(state):\n    return state"


def test_get_callable_source_returns_none_for_syntax_error(tmp_path: Path) -> None:
    _write(tmp_path, "mod.py", "def bad(:\n")

    assert get_callable_source(tmp_path, "mod:bad") is None
