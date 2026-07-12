"""Resolve `module.path:attribute` references to Python objects at compile
time. Shared by tool bindings (FR-1.4) and the custom-code escape hatch
(FR-1.6, ADR-004).
"""

import importlib
import os
import sys


class HandlerResolutionError(Exception):
    """Raised when a `module.path:attribute` reference cannot be resolved."""


def _ensure_cwd_importable() -> None:
    # The installed `agentdraft` console script sets sys.path[0] to its own
    # install directory, not the caller's cwd (unlike `python -c`/`python -m`),
    # so a user's own tool/handler modules next to their schema file would
    # otherwise never resolve.
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)


def resolve_reference(ref: str) -> object:
    """Import `module.path` and return its `attribute`, per a `module.path:attribute` ref."""
    module_path, sep, attr_name = ref.partition(":")
    if not sep:
        raise HandlerResolutionError(
            f"{ref!r} is not a valid reference - expected the form 'module.path:attribute'"
        )
    _ensure_cwd_importable()
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise HandlerResolutionError(f"could not import module {module_path!r}: {exc}") from exc
    try:
        return getattr(module, attr_name)
    except AttributeError as exc:
        raise HandlerResolutionError(
            f"module {module_path!r} has no attribute {attr_name!r}"
        ) from exc
