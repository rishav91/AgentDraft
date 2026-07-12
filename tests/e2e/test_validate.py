from pathlib import Path

from click.testing import CliRunner

from agentdraft.cli import main

FIXTURE = Path(__file__).parent.parent / "fixtures" / "skeleton.yaml"
BAD_FIXTURE = Path(__file__).parent.parent / "fixtures" / "invalid_provider.yaml"


def test_agentdraft_validate_accepts_valid_schema() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(FIXTURE)])

    assert result.exit_code == 0
    assert "valid" in result.output


def test_agentdraft_validate_rejects_invalid_schema() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(BAD_FIXTURE)])

    assert result.exit_code != 0
    assert "unrecognized provider" in result.output
    assert "Traceback" not in result.output
