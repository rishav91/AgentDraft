from click.testing import CliRunner

from agentdraft.cli import main


def test_agentdraft_init_defaults_to_cwd_and_anthropic() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["init"])

        assert result.exit_code == 0
        assert "created" in result.output
        assert "ANTHROPIC_API_KEY" in result.output
        assert "agentdraft validate" in result.output


def test_agentdraft_init_explicit_dest_and_openai_provider() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["init", "my-agent", "--provider", "openai"])

        assert result.exit_code == 0
        assert "OPENAI_API_KEY" in result.output

        result = runner.invoke(main, ["validate", "my-agent/schema.yaml"])
        assert result.exit_code == 0
        assert "valid" in result.output


def test_agentdraft_init_refuses_to_overwrite_without_force() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        result = runner.invoke(main, ["init"])

        assert result.exit_code == 1
        assert "existing file(s)" in result.output
        assert "--force" in result.output


def test_agentdraft_init_force_overwrites() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        result = runner.invoke(main, ["init", "--force"])

        assert result.exit_code == 0
        assert "created" in result.output
