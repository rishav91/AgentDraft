from pathlib import Path

import pytest

from agc.store import STATE_DB_PATH, ensure_local_store_dir


def test_ensure_local_store_dir_creates_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    db_path = ensure_local_store_dir()

    assert db_path == STATE_DB_PATH
    assert (tmp_path / ".agc").is_dir()


def test_ensure_local_store_dir_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    ensure_local_store_dir()
    ensure_local_store_dir()  # must not raise if the directory already exists

    assert (tmp_path / ".agc").is_dir()
