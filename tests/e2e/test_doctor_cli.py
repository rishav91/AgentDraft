from pathlib import Path

from click.testing import CliRunner

from agentdraft.cli import main

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_agentdraft_doctor_with_no_schema_checks_general_only() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["doctor"])

    assert result.exit_code == 0
    assert "Python" in result.output


def test_agentdraft_doctor_reports_missing_provider_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", str(FIXTURES / "tool_calling.yaml")])

    assert result.exit_code == 1
    assert "MISSING" in result.output
    assert "ANTHROPIC_API_KEY" in result.output


def test_agentdraft_doctor_passes_when_key_present(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", str(FIXTURES / "tool_calling.yaml")])

    assert result.exit_code == 0
    assert "MISSING" not in result.output


def test_agentdraft_doctor_rejects_invalid_schema() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", str(FIXTURES / "invalid_provider.yaml")])

    assert result.exit_code == 1
    assert "unrecognized provider" in result.output
