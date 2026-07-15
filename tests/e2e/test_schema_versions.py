from pathlib import Path

from click.testing import CliRunner

from agc.cli import main

FIXTURE = Path(__file__).parent.parent / "fixtures" / "skeleton.yaml"


def test_schema_log_reports_no_revisions_for_a_never_saved_schema() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("schema.yaml").write_text(FIXTURE.read_text())
        result = runner.invoke(main, ["schema", "log", "schema.yaml"])

    assert result.exit_code == 0
    assert "no recorded revisions" in result.output


def test_schema_log_lists_revisions_after_a_save() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        schema_path = Path("schema.yaml")
        schema_path.write_text(FIXTURE.read_text())

        # Drive save_schema directly through the library - the same function the
        # canvas API server's POST /api/save funnels through (FR-9.1, ADR-008).
        from agc.schema import load_schema, save_schema

        schema = load_schema(schema_path)
        schema.nodes[0].llm.system = "changed"  # type: ignore[union-attr]
        save_schema(schema, schema_path)

        result = runner.invoke(main, ["schema", "log", str(schema_path)])

    assert result.exit_code == 0
    assert "revision 1" in result.output


def test_schema_diff_shows_unified_diff_between_revisions() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        schema_path = Path("schema.yaml")
        schema_path.write_text(FIXTURE.read_text())

        from agc.schema import load_schema, save_schema

        schema = load_schema(schema_path)
        save_schema(schema, schema_path)  # revision 1
        schema.nodes[0].llm.system = "a different system prompt"  # type: ignore[union-attr]
        save_schema(schema, schema_path)  # revision 2

        result = runner.invoke(main, ["schema", "diff", str(schema_path), "1", "2"])

    assert result.exit_code == 0
    lines = result.output.splitlines()
    removed = [line for line in lines if line.startswith("-") and "system" in line]
    added = [line for line in lines if line.startswith("+") and "system" in line]
    assert removed and "terse" in removed[0]
    assert added and "a different system prompt" in added[0]


def test_schema_diff_exits_1_on_unknown_revision() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        schema_path = Path("schema.yaml")
        schema_path.write_text(FIXTURE.read_text())

        from agc.schema import load_schema, save_schema

        save_schema(load_schema(schema_path), schema_path)

        result = runner.invoke(main, ["schema", "diff", str(schema_path), "1", "99"])

    assert result.exit_code == 1
    assert "no revision 99" in result.output


def test_schema_revert_restores_an_older_revision_as_a_new_one() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        schema_path = Path("schema.yaml")
        schema_path.write_text(FIXTURE.read_text())

        from agc.schema import load_schema, save_schema

        schema = load_schema(schema_path)
        save_schema(schema, schema_path)  # revision 1
        schema.nodes[0].llm.system = "a different system prompt"  # type: ignore[union-attr]
        save_schema(schema, schema_path)  # revision 2

        result = runner.invoke(main, ["schema", "revert", str(schema_path), "1"])
        log_result = runner.invoke(main, ["schema", "log", str(schema_path)])
        reverted_content = schema_path.read_text()

    assert result.exit_code == 0
    assert "reverted to revision 1's content as new revision 3" in result.output
    assert "terse" in reverted_content
    assert "revision 3" in log_result.output


def test_schema_revert_is_a_no_op_when_already_at_that_content() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        schema_path = Path("schema.yaml")
        schema_path.write_text(FIXTURE.read_text())

        from agc.schema import load_schema, save_schema

        save_schema(load_schema(schema_path), schema_path)  # revision 1

        result = runner.invoke(main, ["schema", "revert", str(schema_path), "1"])

    assert result.exit_code == 0
    assert "already at revision 1's content" in result.output


def test_schema_revert_exits_1_on_unknown_revision() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        schema_path = Path("schema.yaml")
        schema_path.write_text(FIXTURE.read_text())

        from agc.schema import load_schema, save_schema

        save_schema(load_schema(schema_path), schema_path)

        result = runner.invoke(main, ["schema", "revert", str(schema_path), "99"])

    assert result.exit_code == 1
    assert "no revision 99" in result.output
