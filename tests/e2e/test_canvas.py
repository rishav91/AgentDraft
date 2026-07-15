from pathlib import Path

from click.testing import CliRunner

from agc.cli import main

BAD_FIXTURE = Path(__file__).parent.parent / "fixtures" / "invalid_provider.yaml"


def test_agc_canvas_exits_1_on_invalid_schema_without_starting_server() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["canvas", str(BAD_FIXTURE)])

    assert result.exit_code == 1
    assert "unrecognized provider" in result.output
    assert "Traceback" not in result.output
