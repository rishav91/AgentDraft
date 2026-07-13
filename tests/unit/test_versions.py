from pathlib import Path

import pytest

from agentdraft.versions import (
    RevisionNotFoundError,
    diff_revisions,
    get_revision,
    list_revisions,
    record_revision,
)

# tests/conftest.py's autouse _isolate_cwd fixture already sandboxes every test's
# cwd (and so .agentdraft/) into its own tmp_path.


def test_record_revision_creates_revision_one() -> None:
    rev = record_revision("schema.yaml", "schema_version: 1\n")

    assert rev is not None
    assert rev.revision == 1
    assert rev.content == "schema_version: 1\n"


def test_record_revision_skips_unchanged_content() -> None:
    record_revision("schema.yaml", "schema_version: 1\n")

    rev = record_revision("schema.yaml", "schema_version: 1\n")

    assert rev is None
    assert len(list_revisions("schema.yaml")) == 1


def test_record_revision_increments_on_changed_content() -> None:
    record_revision("schema.yaml", "schema_version: 1\nnodes: []\n")

    rev = record_revision("schema.yaml", "schema_version: 1\nnodes: [x]\n")

    assert rev is not None
    assert rev.revision == 2


def test_record_revision_tracks_paths_independently() -> None:
    record_revision("a.yaml", "a v1\n")
    record_revision("b.yaml", "b v1\n")
    record_revision("a.yaml", "a v2\n")

    assert [r.revision for r in list_revisions("a.yaml")] == [2, 1]
    assert [r.revision for r in list_revisions("b.yaml")] == [1]


def test_record_revision_normalizes_path_outside_cwd(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside_schema.yaml"
    outside.write_text("schema_version: 1\n")

    rev = record_revision(outside, "content\n")

    assert rev is not None
    assert list_revisions(outside)[0].revision == 1


def test_list_revisions_empty_for_unknown_path() -> None:
    assert list_revisions("never-saved.yaml") == []


def test_list_revisions_most_recent_first() -> None:
    record_revision("schema.yaml", "v1\n")
    record_revision("schema.yaml", "v2\n")
    record_revision("schema.yaml", "v3\n")

    revisions = list_revisions("schema.yaml")

    assert [r.revision for r in revisions] == [3, 2, 1]
    assert [r.content for r in revisions] == ["v3\n", "v2\n", "v1\n"]


def test_get_revision_returns_none_for_unknown_revision() -> None:
    record_revision("schema.yaml", "v1\n")

    assert get_revision("schema.yaml", 99) is None


def test_get_revision_returns_matching_revision() -> None:
    record_revision("schema.yaml", "v1\n")
    record_revision("schema.yaml", "v2\n")

    rev = get_revision("schema.yaml", 1)

    assert rev is not None
    assert rev.content == "v1\n"


def test_diff_revisions_produces_unified_diff() -> None:
    record_revision("schema.yaml", "line one\nline two\n")
    record_revision("schema.yaml", "line one\nline TWO\n")

    diff = diff_revisions("schema.yaml", 1, 2)

    assert "-line two" in diff
    assert "+line TWO" in diff
    assert "revision 1" in diff
    assert "revision 2" in diff


def test_diff_revisions_raises_on_missing_revision_a() -> None:
    record_revision("schema.yaml", "v1\n")

    with pytest.raises(RevisionNotFoundError, match="no revision 99"):
        diff_revisions("schema.yaml", 99, 1)


def test_diff_revisions_raises_on_missing_revision_b() -> None:
    record_revision("schema.yaml", "v1\n")

    with pytest.raises(RevisionNotFoundError, match="no revision 99"):
        diff_revisions("schema.yaml", 1, 99)
