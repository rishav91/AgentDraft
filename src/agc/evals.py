"""Deterministic eval/regression harness (FR-8, ADR-012): a separate YAML file lists
named cases against one schema - an initial state input and one or more assertions on
final graph state. Every assertion type is structural (field equality, substring,
regex via a dotted/indexed path) - no LLM-as-judge, no non-deterministic check
(ADR-012 alternatives), so a case's result is reproducible on every run (NFR-9.1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_ASSERTION_KINDS = ("equals", "contains", "matches")


class EvalsFileError(Exception):
    """Raised when an evals file is malformed (FR-8.1) - reported before any case runs."""


class PathResolutionError(Exception):
    """Raised when an assertion's path doesn't resolve against final graph state."""


@dataclass(frozen=True)
class Assertion:
    path: str
    kind: str  # one of _ASSERTION_KINDS
    expected: Any


@dataclass(frozen=True)
class EvalCase:
    name: str
    input: Any  # a human-message string (shorthand, like `run`'s MESSAGE), or a raw state dict
    assertions: list[Assertion]


@dataclass(frozen=True)
class AssertionResult:
    passed: bool
    message: str


@dataclass(frozen=True)
class CaseResult:
    name: str
    passed: bool
    assertion_results: list[AssertionResult]


def load_evals_file(path: str | Path) -> list[EvalCase]:
    """Parse and validate an evals YAML file into a list of cases (FR-8.1).

    Raises `EvalsFileError` with a field-specific message on any structural problem
    (missing `schema`/`cases`, an unresolvable schema path, a malformed case or
    assertion) - matching `NFR-2.1`'s error-quality bar, before any case runs.
    """
    evals_path = Path(path)
    raw: Any = yaml.safe_load(evals_path.read_text())
    if not isinstance(raw, dict):
        raise EvalsFileError(f"{path}: evals file must be a YAML mapping")

    schema_field = raw.get("schema")
    if not schema_field:
        raise EvalsFileError(f"{path}: 'schema' is required")
    if not (evals_path.parent / schema_field).is_file():
        raise EvalsFileError(f"{path}: schema: {schema_field!r} does not resolve to a file")

    raw_cases = raw.get("cases")
    if not raw_cases:
        raise EvalsFileError(f"{path}: 'cases' is required and must be a non-empty list")
    if not isinstance(raw_cases, list):
        raise EvalsFileError(f"{path}: 'cases' must be a list")

    cases: list[EvalCase] = []
    seen_names: set[str] = set()
    for i, raw_case in enumerate(raw_cases):
        if not isinstance(raw_case, dict):
            raise EvalsFileError(f"{path}: cases[{i}]: must be a mapping")

        name = raw_case.get("name")
        if not name:
            raise EvalsFileError(f"{path}: cases[{i}]: 'name' is required")
        if name in seen_names:
            raise EvalsFileError(f"{path}: cases: duplicate case name {name!r}")
        seen_names.add(name)

        if "input" not in raw_case:
            raise EvalsFileError(f"{path}: cases[{name!r}]: 'input' is required")

        raw_assertions = raw_case.get("assert")
        if not raw_assertions:
            raise EvalsFileError(
                f"{path}: cases[{name!r}]: 'assert' is required and must be a non-empty list"
            )
        if not isinstance(raw_assertions, list):
            raise EvalsFileError(f"{path}: cases[{name!r}]: 'assert' must be a list")

        assertions = [
            _parse_assertion(path, name, j, raw_assertion)
            for j, raw_assertion in enumerate(raw_assertions)
        ]
        cases.append(EvalCase(name=name, input=raw_case["input"], assertions=assertions))

    return cases


def _parse_assertion(path: str | Path, case_name: str, index: int, raw: Any) -> Assertion:
    if not isinstance(raw, dict):
        raise EvalsFileError(f"{path}: cases[{case_name!r}].assert[{index}]: must be a mapping")

    assertion_path = raw.get("path")
    if not assertion_path:
        raise EvalsFileError(f"{path}: cases[{case_name!r}].assert[{index}]: 'path' is required")

    present_kinds = [kind for kind in _ASSERTION_KINDS if kind in raw]
    if len(present_kinds) != 1:
        raise EvalsFileError(
            f"{path}: cases[{case_name!r}].assert[{index}]: exactly one of "
            f"{'/'.join(_ASSERTION_KINDS)} is required, got {present_kinds or 'none'}"
        )
    kind = present_kinds[0]
    return Assertion(path=assertion_path, kind=kind, expected=raw[kind])


def _tokenize_path(path: str) -> list[str | int]:
    """Split a dotted/indexed path (e.g. `messages[-1].content`) into key/index tokens."""
    tokens: list[str | int] = []
    buf = ""
    i = 0
    while i < len(path):
        char = path[i]
        if char == ".":
            if buf:
                tokens.append(buf)
                buf = ""
            i += 1
        elif char == "[":
            if buf:
                tokens.append(buf)
                buf = ""
            end = path.find("]", i)
            if end == -1:
                raise PathResolutionError(f"{path!r}: unterminated '['")
            index_str = path[i + 1 : end]
            try:
                tokens.append(int(index_str))
            except ValueError:
                raise PathResolutionError(
                    f"{path!r}: index {index_str!r} is not an integer"
                ) from None
            i = end + 1
        else:
            buf += char
            i += 1
    if buf:
        tokens.append(buf)
    if not tokens:
        raise PathResolutionError(f"{path!r}: empty path")
    return tokens


def resolve_path(state: Any, path: str) -> Any:
    """Resolve PATH against final graph STATE: dict-key/list-index access for state
    fields (e.g. `messages`, `edge_visits`), attribute access for the LangChain
    message objects state fields hold (e.g. `messages[-1].content`) (`FR-8.3`).
    """
    value = state
    for token in _tokenize_path(path):
        if isinstance(token, int):
            if not isinstance(value, list | tuple):
                raise PathResolutionError(
                    f"{path!r}: cannot index {type(value).__name__} with [{token}]"
                )
            try:
                value = value[token]
            except IndexError:
                raise PathResolutionError(f"{path!r}: index {token} out of range") from None
        elif isinstance(value, dict):
            if token not in value:
                raise PathResolutionError(f"{path!r}: no key {token!r}")
            value = value[token]
        elif hasattr(value, token):
            value = getattr(value, token)
        else:
            raise PathResolutionError(
                f"{path!r}: no attribute/key {token!r} on {type(value).__name__}"
            )
    return value


def check_assertion(state: Any, assertion: Assertion) -> AssertionResult:
    """Evaluate one ASSERTION against final graph STATE (`FR-8.3`)."""
    try:
        actual = resolve_path(state, assertion.path)
    except PathResolutionError as exc:
        return AssertionResult(False, str(exc))

    if assertion.kind == "equals":
        passed = actual == assertion.expected
        detail = f"{assertion.path} equals {assertion.expected!r}"
    elif assertion.kind == "contains":
        passed = str(assertion.expected) in str(actual)
        detail = f"{assertion.path} contains {assertion.expected!r}"
    else:
        passed = re.search(str(assertion.expected), str(actual)) is not None
        detail = f"{assertion.path} matches {assertion.expected!r}"

    status = "ok" if passed else "FAIL"
    return AssertionResult(passed, f"{status}: {detail} (got {actual!r})")


def run_case(graph: Any, case: EvalCase) -> CaseResult:
    """Invoke GRAPH once with CASE's input and check all of its assertions against
    the resulting final state. A LangGraph runtime error propagates uncaught, same as
    `run` (`FR-8.4`) - only assertion failures are this function's own "failure".
    """
    input_ = {"messages": [("human", case.input)]} if isinstance(case.input, str) else case.input
    final_state = graph.invoke(input_)
    results = [check_assertion(final_state, assertion) for assertion in case.assertions]
    return CaseResult(
        name=case.name, passed=all(r.passed for r in results), assertion_results=results
    )
