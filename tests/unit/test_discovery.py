from pathlib import Path

import pytest

from agc import discovery
from agc.discovery import discover_callables, discover_schema_files, get_callable_source


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


def test_scan_dirs_restricts_which_subdirectories_are_walked(tmp_path: Path) -> None:
    _write(tmp_path, "handlers/route.py", "def wanted(state): return state\n")
    _write(tmp_path, "tests/test_something.py", "def test_unwanted(): pass\n")

    result = discover_callables(tmp_path, scan_dirs=[Path("handlers")])

    assert result == ["handlers.route:wanted"]


def test_scan_dirs_module_paths_stay_relative_to_import_root(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/handlers/route.py", "def wanted(state): return state\n")

    result = discover_callables(tmp_path, scan_dirs=[Path("pkg/handlers")])

    assert result == ["pkg.handlers.route:wanted"]


def test_scan_dirs_ignores_a_nonexistent_directory(tmp_path: Path) -> None:
    _write(tmp_path, "handlers/route.py", "def wanted(state): return state\n")

    result = discover_callables(tmp_path, scan_dirs=[Path("handlers"), Path("does_not_exist")])

    assert result == ["handlers.route:wanted"]


def test_scan_dirs_deduplicates_overlapping_directories(tmp_path: Path) -> None:
    _write(tmp_path, "handlers/route.py", "def wanted(state): return state\n")

    result = discover_callables(
        tmp_path, scan_dirs=[Path("handlers"), Path("handlers"), Path(".")]
    )

    assert result == ["handlers.route:wanted"]


def test_scan_dirs_skips_a_directory_outside_import_root(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    _write(outside, "route.py", "def wanted(state): return state\n")
    project_root = tmp_path / "project"
    project_root.mkdir()

    result = discover_callables(project_root, scan_dirs=[outside])

    assert result == []


def test_excludes_agcs_own_package_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package_dir = tmp_path / "project" / "vendored" / "agc"
    _write(tmp_path, "project/vendored/agc/compiler.py", "def schema_structure(): pass\n")
    _write(tmp_path, "project/handlers.py", "def my_handler(state): return state\n")
    monkeypatch.setattr(discovery, "_AGC_PACKAGE_DIR", package_dir)

    assert discover_callables(tmp_path / "project") == ["handlers:my_handler"]


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


_VALID_SCHEMA = (
    "schema_version: 1\nnodes:\n  - id: chat\n    llm:\n      provider: anthropic\n      model: x\n"
)


def test_discover_schema_files_reports_node_count_for_a_valid_schema(tmp_path: Path) -> None:
    _write(tmp_path, "schema.yaml", _VALID_SCHEMA)

    assert discover_schema_files(tmp_path) == [
        {"path": "schema.yaml", "valid": True, "node_count": 1}
    ]


def test_discover_schema_files_finds_yml_extension_too(tmp_path: Path) -> None:
    _write(tmp_path, "schema.yml", _VALID_SCHEMA)

    assert discover_schema_files(tmp_path) == [
        {"path": "schema.yml", "valid": True, "node_count": 1}
    ]


def test_discover_schema_files_marks_malformed_yaml_invalid(tmp_path: Path) -> None:
    _write(tmp_path, "broken.yaml", "nodes: [this is not: valid: yaml\n")

    assert discover_schema_files(tmp_path) == [
        {"path": "broken.yaml", "valid": False, "node_count": None}
    ]


def test_discover_schema_files_marks_structurally_invalid_schema_invalid(tmp_path: Path) -> None:
    _write(tmp_path, "invalid.yaml", "schema_version: 99\nnodes: []\n")

    assert discover_schema_files(tmp_path) == [
        {"path": "invalid.yaml", "valid": False, "node_count": None}
    ]


def test_discover_schema_files_skips_excluded_directories(tmp_path: Path) -> None:
    _write(tmp_path, ".venv/lib/thing.yaml", _VALID_SCHEMA)
    _write(tmp_path, "schema.yaml", _VALID_SCHEMA)

    assert discover_schema_files(tmp_path) == [
        {"path": "schema.yaml", "valid": True, "node_count": 1}
    ]


def test_discover_schema_files_respects_scan_dirs(tmp_path: Path) -> None:
    _write(tmp_path, "schemas/a.yaml", _VALID_SCHEMA)
    _write(tmp_path, "other/b.yaml", _VALID_SCHEMA)

    result = discover_schema_files(tmp_path, scan_dirs=[Path("schemas")])

    assert result == [{"path": "schemas/a.yaml", "valid": True, "node_count": 1}]


def test_discover_schema_files_results_are_sorted(tmp_path: Path) -> None:
    _write(tmp_path, "b.yaml", _VALID_SCHEMA)
    _write(tmp_path, "a.yaml", _VALID_SCHEMA)

    result = discover_schema_files(tmp_path)

    assert [entry["path"] for entry in result] == ["a.yaml", "b.yaml"]


def test_discover_schema_files_ignores_a_nonexistent_scan_dir(tmp_path: Path) -> None:
    _write(tmp_path, "schemas/a.yaml", _VALID_SCHEMA)

    result = discover_schema_files(tmp_path, scan_dirs=[Path("schemas"), Path("does_not_exist")])

    assert result == [{"path": "schemas/a.yaml", "valid": True, "node_count": 1}]


def test_discover_schema_files_deduplicates_overlapping_scan_dirs(tmp_path: Path) -> None:
    _write(tmp_path, "schemas/a.yaml", _VALID_SCHEMA)

    result = discover_schema_files(tmp_path, scan_dirs=[Path("schemas"), Path("schemas")])

    assert result == [{"path": "schemas/a.yaml", "valid": True, "node_count": 1}]


def test_discover_schema_files_skips_a_scan_dir_outside_import_root(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    _write(outside, "a.yaml", _VALID_SCHEMA)
    project_root = tmp_path / "project"
    project_root.mkdir()

    result = discover_schema_files(project_root, scan_dirs=[outside])

    assert result == []
