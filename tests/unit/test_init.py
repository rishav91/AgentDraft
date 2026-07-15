import importlib.metadata

import pytest

from agentdraft.init import PROVIDER_API_KEY_ENV, ScaffoldExistsError, scaffold


@pytest.mark.parametrize("provider", ["anthropic", "openai"])
def test_scaffold_writes_expected_files(tmp_path, provider) -> None:
    written = scaffold(tmp_path, provider, force=False)

    names = {p.name for p in written}
    assert "schema.yaml" in names
    assert "tools.py" in names
    assert "NOTES.md" in names
    assert ".env.example" in names
    assert "requirements.txt" in names
    if provider == "openai":
        assert "handlers.py" in names
        assert "routing.py" in names
    else:
        assert "handlers.py" not in names
        assert "routing.py" not in names

    for path in written:
        assert path.exists()
        assert path.parent == tmp_path


def test_scaffold_env_example_names_the_right_key(tmp_path) -> None:
    scaffold(tmp_path, "anthropic", force=False)
    assert (tmp_path / ".env.example").read_text() == "ANTHROPIC_API_KEY=\n"

    scaffold(tmp_path / "openai_proj", "openai", force=False)
    assert (tmp_path / "openai_proj" / ".env.example").read_text() == "OPENAI_API_KEY=\n"


def test_scaffold_creates_dest_if_missing(tmp_path) -> None:
    dest = tmp_path / "new-agent"
    assert not dest.exists()

    scaffold(dest, "anthropic", force=False)

    assert dest.is_dir()
    assert (dest / "schema.yaml").exists()


def test_scaffold_refuses_to_overwrite_without_force(tmp_path) -> None:
    scaffold(tmp_path, "anthropic", force=False)

    with pytest.raises(ScaffoldExistsError) as exc_info:
        scaffold(tmp_path, "anthropic", force=False)

    assert "schema.yaml" in exc_info.value.existing


def test_scaffold_overwrites_with_force(tmp_path) -> None:
    scaffold(tmp_path, "anthropic", force=False)
    (tmp_path / "schema.yaml").write_text("corrupted")

    scaffold(tmp_path, "anthropic", force=True)

    assert (tmp_path / "schema.yaml").read_text() != "corrupted"


def test_scaffold_writes_nothing_on_conflict(tmp_path) -> None:
    # A conflict on one file must fail atomically - no partial writes of the rest.
    (tmp_path / "schema.yaml").write_text("pre-existing")

    with pytest.raises(ScaffoldExistsError):
        scaffold(tmp_path, "anthropic", force=False)

    assert (tmp_path / "schema.yaml").read_text() == "pre-existing"
    assert not (tmp_path / "tools.py").exists()
    assert not (tmp_path / ".env.example").exists()


def test_provider_api_key_env_covers_both_providers() -> None:
    assert PROVIDER_API_KEY_ENV["anthropic"] == "ANTHROPIC_API_KEY"
    assert PROVIDER_API_KEY_ENV["openai"] == "OPENAI_API_KEY"


def _fake_version(name: str) -> str:
    return {"agent-draft": "9.9.9", "langchain-core": "1.2.3"}[name]


def test_requirements_txt_pins_installed_agent_draft_and_langchain_core_versions(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(importlib.metadata, "version", _fake_version)

    scaffold(tmp_path, "anthropic", force=False)

    content = (tmp_path / "requirements.txt").read_text()
    assert "agent-draft==9.9.9[examples]" in content
    assert "langchain-core==1.2.3" in content
    assert "vendor/agent_draft-9.9.9-py3-none-any.whl[examples]" in content


def test_requirements_txt_is_identical_across_providers(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(importlib.metadata, "version", _fake_version)

    scaffold(tmp_path / "a", "anthropic", force=False)
    scaffold(tmp_path / "o", "openai", force=False)

    assert (tmp_path / "a" / "requirements.txt").read_text() == (
        tmp_path / "o" / "requirements.txt"
    ).read_text()
