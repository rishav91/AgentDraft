import pytest

from agentdraft.loader import HandlerResolutionError, resolve_reference


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
