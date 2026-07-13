"""AgentDraft loads a `.env` file from cwd on every command invocation
(convenient for LLM API keys), without letting it override an already-set
real environment variable.
"""

import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from agentdraft.cli import main

FIXTURE = Path(__file__).parent.parent / "fixtures" / "skeleton.yaml"


def test_dotenv_is_loaded_from_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENTDRAFT_TEST_VAR", raising=False)
    (tmp_path / ".env").write_text("AGENTDRAFT_TEST_VAR=from-dotenv\n")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(main, ["validate", str(FIXTURE)])

    assert result.exit_code == 0
    assert os.environ["AGENTDRAFT_TEST_VAR"] == "from-dotenv"


def test_dotenv_does_not_override_a_real_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGENTDRAFT_TEST_VAR", "from-shell")
    (tmp_path / ".env").write_text("AGENTDRAFT_TEST_VAR=from-dotenv\n")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(main, ["validate", str(FIXTURE)])

    assert result.exit_code == 0
    assert os.environ["AGENTDRAFT_TEST_VAR"] == "from-shell"


def test_missing_dotenv_is_a_silent_no_op(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(main, ["validate", str(FIXTURE)])

    assert result.exit_code == 0
