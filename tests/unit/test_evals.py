from pathlib import Path
from typing import Any

import pytest

from agc.evals import (
    Assertion,
    EvalCase,
    EvalsFileError,
    PathResolutionError,
    check_assertion,
    load_evals_file,
    resolve_path,
    run_case,
)


def _write(path: Path, content: str) -> Path:
    path.write_text(content)
    return path


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeGraph:
    def __init__(self, final_state: dict[str, Any]) -> None:
        self._final_state = final_state
        self.invoked_with: Any = None

    def invoke(self, input_: Any) -> dict[str, Any]:
        self.invoked_with = input_
        return self._final_state


# --- load_evals_file ---------------------------------------------------------


def test_load_evals_file_parses_a_valid_file(tmp_path: Path) -> None:
    _write(tmp_path / "schema.yaml", "schema_version: 1\n")
    evals_path = _write(
        tmp_path / "evals.yaml",
        """
        schema: schema.yaml
        cases:
          - name: greets
            input: "hi"
            assert:
              - path: messages[-1].content
                equals: "hello"
        """,
    )

    cases = load_evals_file(evals_path)

    assert len(cases) == 1
    assert cases[0].name == "greets"
    assert cases[0].input == "hi"
    assert cases[0].assertions == [
        Assertion(path="messages[-1].content", kind="equals", expected="hello")
    ]


def test_load_evals_file_rejects_non_mapping_file(tmp_path: Path) -> None:
    evals_path = _write(tmp_path / "evals.yaml", "- just\n- a\n- list\n")

    with pytest.raises(EvalsFileError, match="must be a YAML mapping"):
        load_evals_file(evals_path)


def test_load_evals_file_requires_schema_field(tmp_path: Path) -> None:
    evals_path = _write(tmp_path / "evals.yaml", "cases: []\n")

    with pytest.raises(EvalsFileError, match="'schema' is required"):
        load_evals_file(evals_path)


def test_load_evals_file_requires_resolvable_schema_path(tmp_path: Path) -> None:
    evals_path = _write(tmp_path / "evals.yaml", "schema: does-not-exist.yaml\ncases: []\n")

    with pytest.raises(EvalsFileError, match="does not resolve to a file"):
        load_evals_file(evals_path)


def test_load_evals_file_requires_cases(tmp_path: Path) -> None:
    _write(tmp_path / "schema.yaml", "schema_version: 1\n")
    evals_path = _write(tmp_path / "evals.yaml", "schema: schema.yaml\n")

    with pytest.raises(EvalsFileError, match="'cases' is required"):
        load_evals_file(evals_path)


def test_load_evals_file_requires_cases_to_be_a_list(tmp_path: Path) -> None:
    _write(tmp_path / "schema.yaml", "schema_version: 1\n")
    evals_path = _write(tmp_path / "evals.yaml", "schema: schema.yaml\ncases: {a: 1}\n")

    with pytest.raises(EvalsFileError, match="'cases' must be a list"):
        load_evals_file(evals_path)


def test_load_evals_file_rejects_non_mapping_case(tmp_path: Path) -> None:
    _write(tmp_path / "schema.yaml", "schema_version: 1\n")
    evals_path = _write(tmp_path / "evals.yaml", "schema: schema.yaml\ncases:\n  - just a string\n")

    with pytest.raises(EvalsFileError, match=r"cases\[0\]: must be a mapping"):
        load_evals_file(evals_path)


def test_load_evals_file_requires_case_name(tmp_path: Path) -> None:
    _write(tmp_path / "schema.yaml", "schema_version: 1\n")
    evals_path = _write(
        tmp_path / "evals.yaml",
        "schema: schema.yaml\ncases:\n  - input: hi\n    assert: [{path: x, equals: 1}]\n",
    )

    with pytest.raises(EvalsFileError, match="'name' is required"):
        load_evals_file(evals_path)


def test_load_evals_file_rejects_duplicate_case_names(tmp_path: Path) -> None:
    _write(tmp_path / "schema.yaml", "schema_version: 1\n")
    evals_path = _write(
        tmp_path / "evals.yaml",
        """
        schema: schema.yaml
        cases:
          - name: dup
            input: hi
            assert: [{path: x, equals: 1}]
          - name: dup
            input: hi
            assert: [{path: x, equals: 1}]
        """,
    )

    with pytest.raises(EvalsFileError, match="duplicate case name"):
        load_evals_file(evals_path)


def test_load_evals_file_requires_case_input(tmp_path: Path) -> None:
    _write(tmp_path / "schema.yaml", "schema_version: 1\n")
    evals_path = _write(
        tmp_path / "evals.yaml",
        "schema: schema.yaml\ncases:\n  - name: c\n    assert: [{path: x, equals: 1}]\n",
    )

    with pytest.raises(EvalsFileError, match="'input' is required"):
        load_evals_file(evals_path)


def test_load_evals_file_requires_assert(tmp_path: Path) -> None:
    _write(tmp_path / "schema.yaml", "schema_version: 1\n")
    evals_path = _write(
        tmp_path / "evals.yaml", "schema: schema.yaml\ncases:\n  - name: c\n    input: hi\n"
    )

    with pytest.raises(EvalsFileError, match="'assert' is required"):
        load_evals_file(evals_path)


def test_load_evals_file_requires_assert_to_be_a_list(tmp_path: Path) -> None:
    _write(tmp_path / "schema.yaml", "schema_version: 1\n")
    evals_path = _write(
        tmp_path / "evals.yaml",
        "schema: schema.yaml\ncases:\n  - name: c\n    input: hi\n    assert: {a: 1}\n",
    )

    with pytest.raises(EvalsFileError, match="'assert' must be a list"):
        load_evals_file(evals_path)


def test_load_evals_file_rejects_non_mapping_assertion(tmp_path: Path) -> None:
    _write(tmp_path / "schema.yaml", "schema_version: 1\n")
    evals_path = _write(
        tmp_path / "evals.yaml",
        "schema: schema.yaml\ncases:\n  - name: c\n    input: hi\n"
        "    assert:\n      - just a string\n",
    )

    with pytest.raises(EvalsFileError, match=r"assert\[0\]: must be a mapping"):
        load_evals_file(evals_path)


def test_load_evals_file_requires_assertion_path(tmp_path: Path) -> None:
    _write(tmp_path / "schema.yaml", "schema_version: 1\n")
    evals_path = _write(
        tmp_path / "evals.yaml",
        "schema: schema.yaml\ncases:\n  - name: c\n    input: hi\n    assert:\n      - equals: 1\n",
    )

    with pytest.raises(EvalsFileError, match="'path' is required"):
        load_evals_file(evals_path)


def test_load_evals_file_requires_exactly_one_assertion_kind_none(tmp_path: Path) -> None:
    _write(tmp_path / "schema.yaml", "schema_version: 1\n")
    evals_path = _write(
        tmp_path / "evals.yaml",
        "schema: schema.yaml\ncases:\n  - name: c\n    input: hi\n    assert:\n      - path: x\n",
    )

    with pytest.raises(EvalsFileError, match="exactly one of"):
        load_evals_file(evals_path)


def test_load_evals_file_requires_exactly_one_assertion_kind_multiple(tmp_path: Path) -> None:
    _write(tmp_path / "schema.yaml", "schema_version: 1\n")
    evals_path = _write(
        tmp_path / "evals.yaml",
        "schema: schema.yaml\ncases:\n  - name: c\n    input: hi\n"
        "    assert:\n      - path: x\n        equals: 1\n        contains: 2\n",
    )

    with pytest.raises(EvalsFileError, match="exactly one of"):
        load_evals_file(evals_path)


# --- resolve_path -------------------------------------------------------------


def test_resolve_path_dict_key() -> None:
    assert resolve_path({"a": {"b": 1}}, "a.b") == 1


def test_resolve_path_list_index_negative() -> None:
    assert resolve_path({"messages": [1, 2, 3]}, "messages[-1]") == 3


def test_resolve_path_attribute_access() -> None:
    state = {"messages": [_FakeMessage("hi")]}
    assert resolve_path(state, "messages[0].content") == "hi"


def test_resolve_path_missing_dict_key_raises() -> None:
    with pytest.raises(PathResolutionError, match="no key"):
        resolve_path({"a": 1}, "b")


def test_resolve_path_missing_attribute_raises() -> None:
    with pytest.raises(PathResolutionError, match="no attribute/key"):
        resolve_path(_FakeMessage("hi"), "nope")


def test_resolve_path_index_out_of_range_raises() -> None:
    with pytest.raises(PathResolutionError, match="out of range"):
        resolve_path({"messages": [1]}, "messages[5]")


def test_resolve_path_cannot_index_non_sequence_raises() -> None:
    with pytest.raises(PathResolutionError, match="cannot index"):
        resolve_path({"a": 1}, "a[0]")


def test_resolve_path_unterminated_bracket_raises() -> None:
    with pytest.raises(PathResolutionError, match="unterminated"):
        resolve_path({"a": [1]}, "a[0")


def test_resolve_path_non_integer_index_raises() -> None:
    with pytest.raises(PathResolutionError, match="not an integer"):
        resolve_path({"a": [1]}, "a[x]")


def test_resolve_path_empty_path_raises() -> None:
    with pytest.raises(PathResolutionError, match="empty path"):
        resolve_path({"a": 1}, "")


# --- check_assertion ----------------------------------------------------------


def test_check_assertion_equals_pass() -> None:
    result = check_assertion({"a": "x"}, Assertion(path="a", kind="equals", expected="x"))
    assert result.passed


def test_check_assertion_equals_fail() -> None:
    result = check_assertion({"a": "x"}, Assertion(path="a", kind="equals", expected="y"))
    assert not result.passed


def test_check_assertion_contains_pass() -> None:
    result = check_assertion(
        {"a": "hello world"}, Assertion(path="a", kind="contains", expected="world")
    )
    assert result.passed


def test_check_assertion_contains_fail() -> None:
    result = check_assertion(
        {"a": "hello world"}, Assertion(path="a", kind="contains", expected="bye")
    )
    assert not result.passed


def test_check_assertion_matches_pass() -> None:
    result = check_assertion(
        {"a": "hello world"}, Assertion(path="a", kind="matches", expected="^hello")
    )
    assert result.passed


def test_check_assertion_matches_fail() -> None:
    result = check_assertion(
        {"a": "hello world"}, Assertion(path="a", kind="matches", expected="^bye")
    )
    assert not result.passed


def test_check_assertion_unresolvable_path_fails_without_raising() -> None:
    result = check_assertion({"a": 1}, Assertion(path="b", kind="equals", expected=1))
    assert not result.passed
    assert "no key" in result.message


# --- run_case -------------------------------------------------------------


def test_run_case_wraps_string_input_as_human_message() -> None:
    graph = _FakeGraph({"messages": [_FakeMessage("hello")]})
    case = EvalCase(
        name="c",
        input="hi",
        assertions=[Assertion(path="messages[-1].content", kind="equals", expected="hello")],
    )

    result = run_case(graph, case)

    assert result.passed
    assert result.name == "c"
    assert graph.invoked_with == {"messages": [("human", "hi")]}


def test_run_case_passes_dict_input_through_verbatim() -> None:
    graph = _FakeGraph({"messages": [_FakeMessage("hello")]})
    case = EvalCase(
        name="c",
        input={"messages": [("human", "hi")], "edge_visits": {}},
        assertions=[Assertion(path="messages[-1].content", kind="equals", expected="hello")],
    )

    run_case(graph, case)

    assert graph.invoked_with == {"messages": [("human", "hi")], "edge_visits": {}}


def test_run_case_reports_failed_assertions() -> None:
    graph = _FakeGraph({"messages": [_FakeMessage("hello")]})
    case = EvalCase(
        name="c",
        input="hi",
        assertions=[Assertion(path="messages[-1].content", kind="equals", expected="goodbye")],
    )

    result = run_case(graph, case)

    assert not result.passed
    assert len(result.assertion_results) == 1
    assert not result.assertion_results[0].passed
