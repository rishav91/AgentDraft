import json
import shutil
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import pytest

from agentdraft.schema import SUPPORTED_PROVIDERS, load_schema
from agentdraft.server import create_server, run_canvas_server

FIXTURE = Path(__file__).parent.parent / "fixtures" / "comprehensive.yaml"


@pytest.fixture
def running_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[str, Path]]:
    monkeypatch.chdir(tmp_path)  # keep a save's local version-history store (FR-9.1) sandboxed
    schema_path = tmp_path / "schema.yaml"
    shutil.copy(FIXTURE, schema_path)

    server = create_server(schema_path, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        yield base_url, schema_path
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _get(url: str) -> tuple[int, dict[str, object]]:
    try:
        with urllib.request.urlopen(url) as response:  # noqa: S310 - localhost test server
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _post(url: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
    body = json.dumps(payload).encode()
    request = urllib.request.Request(url, data=body, method="POST")  # noqa: S310
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_get_graph_returns_schema_structure(running_server: tuple[str, Path]) -> None:
    base_url, _ = running_server

    status, body = _get(f"{base_url}/api/graph")

    assert status == 200
    assert body["schema_version"] == 1
    assert [n["id"] for n in body["nodes"]] == ["router", "search", "shout"]  # type: ignore[index]


def test_get_providers_returns_the_supported_provider_list(
    running_server: tuple[str, Path],
) -> None:
    base_url, _ = running_server

    status, body = _get(f"{base_url}/api/providers")

    assert status == 200
    assert body == {"providers": SUPPORTED_PROVIDERS}


def test_get_unknown_route_is_404(running_server: tuple[str, Path]) -> None:
    base_url, _ = running_server

    status, body = _get(f"{base_url}/api/nonsense")

    assert status == 404
    assert "errors" in body


def test_post_unknown_route_is_404(running_server: tuple[str, Path]) -> None:
    base_url, _ = running_server

    status, body = _post(f"{base_url}/api/nonsense", {})

    assert status == 404
    assert "errors" in body


def test_post_save_writes_valid_edit_to_disk(running_server: tuple[str, Path]) -> None:
    base_url, schema_path = running_server
    _, graph = _get(f"{base_url}/api/graph")
    graph["nodes"][0]["llm"]["model"] = "claude-opus-4-8"  # type: ignore[index]

    status, body = _post(f"{base_url}/api/save", graph)

    assert status == 200
    assert body == {"ok": True}
    reloaded = load_schema(schema_path)
    assert reloaded.nodes[0].llm is not None
    assert reloaded.nodes[0].llm.model == "claude-opus-4-8"


@pytest.fixture
def rooted_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[str, Path]]:
    """Like `running_server`, but with import_root pinned to tmp_path (not cwd),
    so a test can write sibling schema files that /api/schemas and /api/open
    can actually see.
    """
    monkeypatch.chdir(tmp_path)  # keep a save's local version-history store (FR-9.1) sandboxed
    schema_path = tmp_path / "schema.yaml"
    shutil.copy(FIXTURE, schema_path)

    server = create_server(schema_path, port=0, import_root=tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        yield base_url, tmp_path
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_get_schemas_lists_yaml_files_and_reports_active(
    rooted_server: tuple[str, Path],
) -> None:
    base_url, _ = rooted_server

    status, body = _get(f"{base_url}/api/schemas")

    assert status == 200
    assert body["active"] == "schema.yaml"
    schemas = body["schemas"]  # type: ignore[index]
    assert {"path": "schema.yaml", "valid": True, "node_count": 3} in schemas  # type: ignore[operator]


def test_post_open_switches_the_active_schema(rooted_server: tuple[str, Path]) -> None:
    base_url, root = rooted_server
    (root / "other.yaml").write_text(
        "schema_version: 1\nnodes:\n  - id: solo\n    llm:\n      provider: anthropic\n"
        "      model: claude-sonnet-5\n"
    )

    status, body = _post(f"{base_url}/api/open", {"path": "other.yaml"})

    assert status == 200
    assert [n["id"] for n in body["nodes"]] == ["solo"]  # type: ignore[index]

    # subsequent requests now target the newly-opened file
    status, graph = _get(f"{base_url}/api/graph")
    assert [n["id"] for n in graph["nodes"]] == ["solo"]  # type: ignore[index]
    _, schemas_body = _get(f"{base_url}/api/schemas")
    assert schemas_body["active"] == "other.yaml"


def test_post_open_save_writes_to_the_newly_opened_file(
    rooted_server: tuple[str, Path],
) -> None:
    base_url, root = rooted_server
    other_path = root / "other.yaml"
    other_path.write_text(
        "schema_version: 1\nnodes:\n  - id: solo\n    llm:\n      provider: anthropic\n"
        "      model: claude-sonnet-5\n"
    )
    _post(f"{base_url}/api/open", {"path": "other.yaml"})
    _, graph = _get(f"{base_url}/api/graph")
    graph["nodes"][0]["llm"]["model"] = "claude-opus-4-8"  # type: ignore[index]

    status, body = _post(f"{base_url}/api/save", graph)

    assert status == 200
    assert body == {"ok": True}
    reloaded = load_schema(other_path)
    assert reloaded.nodes[0].llm is not None
    assert reloaded.nodes[0].llm.model == "claude-opus-4-8"
    # the original schema file must be untouched
    assert load_schema(root / "schema.yaml").nodes[0].id == "router"


def test_post_open_rejects_a_missing_file(rooted_server: tuple[str, Path]) -> None:
    base_url, _ = rooted_server

    status, body = _post(f"{base_url}/api/open", {"path": "does-not-exist.yaml"})

    assert status == 404
    assert "errors" in body


def test_post_open_rejects_malformed_yaml(rooted_server: tuple[str, Path]) -> None:
    base_url, root = rooted_server
    (root / "broken.yaml").write_text("nodes: [this is not: valid: yaml\n")

    status, body = _post(f"{base_url}/api/open", {"path": "broken.yaml"})

    assert status == 422
    assert "errors" in body


def test_post_open_rejects_a_structurally_invalid_schema(
    rooted_server: tuple[str, Path],
) -> None:
    base_url, root = rooted_server
    (root / "invalid.yaml").write_text("schema_version: 99\nnodes: []\n")

    status, body = _post(f"{base_url}/api/open", {"path": "invalid.yaml"})

    assert status == 422
    assert "errors" in body


def test_post_open_rejects_missing_path_field(rooted_server: tuple[str, Path]) -> None:
    base_url, _ = rooted_server

    status, body = _post(f"{base_url}/api/open", {})

    assert status == 422
    assert "errors" in body


def test_post_open_rejects_malformed_json_body(rooted_server: tuple[str, Path]) -> None:
    base_url, _ = rooted_server
    request = urllib.request.Request(  # noqa: S310
        f"{base_url}/api/open", data=b"not json", method="POST"
    )
    try:
        with urllib.request.urlopen(request) as response:  # noqa: S310
            status, body = response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        status, body = exc.code, json.loads(exc.read())

    assert status == 422
    assert "errors" in body


def test_get_schemas_reports_absolute_active_path_when_outside_import_root(
    tmp_path: Path,
) -> None:
    schema_path = tmp_path / "outside_schema.yaml"
    shutil.copy(FIXTURE, schema_path)
    project_root = tmp_path / "project"
    project_root.mkdir()

    server = create_server(schema_path, port=0, import_root=project_root)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_address[1]}"
        status, body = _get(f"{base_url}/api/schemas")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert status == 200
    assert body["active"] == str(schema_path)


def test_post_save_round_trips_max_visits_and_fallback(running_server: tuple[str, Path]) -> None:
    base_url, schema_path = running_server
    _, graph = _get(f"{base_url}/api/graph")
    conditional = next(e for e in graph["edges"] if e["kind"] == "conditional")  # type: ignore[index]
    conditional["max_visits"] = 3
    conditional["fallback"] = "negative"

    status, body = _post(f"{base_url}/api/save", graph)

    assert status == 200
    assert body == {"ok": True}
    reloaded = load_schema(schema_path)
    saved_edge = next(e for e in reloaded.edges if e.condition is not None)
    assert saved_edge.max_visits == 3
    assert saved_edge.fallback == "negative"


def test_post_save_rejects_invalid_edit_and_leaves_file_unchanged(
    running_server: tuple[str, Path],
) -> None:
    base_url, schema_path = running_server
    before = schema_path.read_text()
    _, graph = _get(f"{base_url}/api/graph")
    graph["nodes"][0]["llm"]["provider"] = "not-a-real-provider"  # type: ignore[index]

    status, body = _post(f"{base_url}/api/save", graph)

    assert status == 422
    assert any("unrecognized provider" in err for err in body["errors"])  # type: ignore[union-attr]
    assert schema_path.read_text() == before


def test_post_save_rejects_structurally_invalid_payload(
    running_server: tuple[str, Path],
) -> None:
    base_url, schema_path = running_server
    before = schema_path.read_text()

    status, body = _post(f"{base_url}/api/save", {"nodes": [{"kind": "llm"}]})

    assert status == 422
    assert "errors" in body
    assert schema_path.read_text() == before


def test_post_save_rejects_malformed_json_body(running_server: tuple[str, Path]) -> None:
    base_url, schema_path = running_server
    before = schema_path.read_text()
    request = urllib.request.Request(  # noqa: S310
        f"{base_url}/api/save", data=b"not json", method="POST"
    )
    try:
        with urllib.request.urlopen(request) as response:  # noqa: S310
            status, body = response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        status, body = exc.code, json.loads(exc.read())

    assert status == 422
    assert "errors" in body
    assert schema_path.read_text() == before


def test_options_request_returns_cors_headers(running_server: tuple[str, Path]) -> None:
    base_url, _ = running_server
    request = urllib.request.Request(f"{base_url}/api/graph", method="OPTIONS")  # noqa: S310

    with urllib.request.urlopen(request) as response:  # noqa: S310
        assert response.status == 204
        assert response.headers["Access-Control-Allow-Origin"] == "*"
        assert "POST" in response.headers["Access-Control-Allow-Methods"]


def test_get_graph_reports_validation_error_if_file_becomes_invalid_on_disk(
    running_server: tuple[str, Path],
) -> None:
    base_url, schema_path = running_server
    schema_path.write_text("schema_version: 99\nnodes: []\n")

    status, body = _get(f"{base_url}/api/graph")

    assert status == 422
    assert "errors" in body


def test_get_callables_scans_the_configured_root(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.yaml"
    shutil.copy(FIXTURE, schema_path)
    project_root = tmp_path / "project"
    (project_root / "pkg").mkdir(parents=True)
    (project_root / "pkg" / "handlers.py").write_text("def route(state):\n    return state\n")

    server = create_server(schema_path, port=0, import_root=project_root)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_address[1]}"
        status, body = _get(f"{base_url}/api/callables")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert status == 200
    assert body == {"callables": ["pkg.handlers:route"]}


def test_get_callables_respects_scan_dirs_restriction(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.yaml"
    shutil.copy(FIXTURE, schema_path)
    project_root = tmp_path / "project"
    (project_root / "handlers").mkdir(parents=True)
    (project_root / "handlers" / "route.py").write_text("def wanted(state): return state\n")
    (project_root / "tests").mkdir(parents=True)
    (project_root / "tests" / "test_something.py").write_text("def test_unwanted(): pass\n")

    server = create_server(
        schema_path, port=0, import_root=project_root, scan_dirs=[Path("handlers")]
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_address[1]}"
        status, body = _get(f"{base_url}/api/callables")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert status == 200
    # Module path is still relative to import_root (handlers.route), not "route" -
    # scan_dirs narrows which files get walked, not what a found ref resolves to.
    assert body == {"callables": ["handlers.route:wanted"]}


def test_get_source_returns_the_callables_body(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.yaml"
    shutil.copy(FIXTURE, schema_path)
    project_root = tmp_path / "project"
    (project_root / "pkg").mkdir(parents=True)
    (project_root / "pkg" / "handlers.py").write_text("def route(state):\n    return state\n")

    server = create_server(schema_path, port=0, import_root=project_root)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_address[1]}"
        status, body = _get(f"{base_url}/api/source?ref=pkg.handlers:route")
        missing_status, missing_body = _get(f"{base_url}/api/source?ref=pkg.handlers:nope")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert status == 200
    assert body == {"source": "def route(state):\n    return state"}
    assert missing_status == 404
    assert "errors" in missing_body


def test_run_canvas_server_prints_url_and_stops_on_keyboard_interrupt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    schema_path = tmp_path / "schema.yaml"
    shutil.copy(FIXTURE, schema_path)

    with patch.object(ThreadingHTTPServer, "serve_forever", side_effect=KeyboardInterrupt):
        run_canvas_server(schema_path, port=0)

    output = capsys.readouterr().out
    assert "AGENTDRAFT_CANVAS_URL=http://127.0.0.1:" in output
    assert "stopping" in output
