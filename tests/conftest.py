from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run every test from a fresh tmp_path cwd, so the local `.agc/` store
    (checkpointing `ADR-009`, schema version history `FR-9`, run history `FR-6`)
    never pollutes the real repo checkout - any test that needs its own separate
    tmp_path may still request one and chdir further, same as before.
    """
    monkeypatch.chdir(tmp_path)
