import sys
from pathlib import Path

import pytest

from agc.loader import HandlerResolutionError, resolve_reference


def test_resolve_reference_returns_the_target_object() -> None:
    tool = resolve_reference("tests.support.tools:echo")

    assert tool.name == "echo"


def test_resolve_reference_rejects_missing_colon() -> None:
    with pytest.raises(HandlerResolutionError, match="expected the form"):
        resolve_reference("tests.support.tools.echo")


def test_resolve_reference_rejects_unimportable_module() -> None:
    with pytest.raises(HandlerResolutionError, match="could not import module"):
        resolve_reference("no.such.module:thing")


def test_resolve_reference_rejects_missing_attribute() -> None:
    with pytest.raises(HandlerResolutionError, match="no attribute 'nope'"):
        resolve_reference("tests.support.tools:nope")


def test_resolve_reference_finds_modules_next_to_the_caller_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "my_local_tools.py").write_text("def greet():\n    return 'hi'\n")
    monkeypatch.chdir(tmp_path)
    assert str(tmp_path) not in sys.path

    try:
        greet = resolve_reference("my_local_tools:greet")
        assert greet() == "hi"
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("my_local_tools", None)
