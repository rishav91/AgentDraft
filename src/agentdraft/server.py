"""Local HTTP server backing the canvas's editing session (Phase 2.2, FR-4.3, ADR-008).

Single-user, localhost-only, no auth - the same trust boundary the custom-code
escape hatch already accepts (NFR-4.1, NFR-4.2): the schema author has full local
code execution regardless. Started by `agentdraft canvas <schema>`; stopped with
Ctrl+C.
"""

import json
from collections.abc import Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from pydantic import ValidationError

from agentdraft.compiler import schema_from_structure, schema_structure
from agentdraft.discovery import discover_callables, get_callable_source
from agentdraft.schema import format_validation_errors, load_schema, save_schema


def _handler_for(
    schema_path: Path, import_root: Path, scan_dirs: Sequence[Path]
) -> type[BaseHTTPRequestHandler]:
    class CanvasRequestHandler(BaseHTTPRequestHandler):
        def _write_json(self, status: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_GET(self) -> None:
            parsed = urlsplit(self.path)
            if parsed.path == "/api/callables":
                self._write_json(200, {"callables": discover_callables(import_root, scan_dirs)})
                return
            if parsed.path == "/api/source":
                ref = parse_qs(parsed.query).get("ref", [""])[0]
                source = get_callable_source(import_root, ref)
                if source is None:
                    self._write_json(404, {"errors": [f"no source found for {ref!r}"]})
                    return
                self._write_json(200, {"source": source})
                return
            if parsed.path != "/api/graph":
                self._write_json(404, {"errors": [f"no such route: GET {parsed.path}"]})
                return
            try:
                schema = load_schema(schema_path)
            except ValidationError as exc:
                self._write_json(422, {"errors": format_validation_errors(exc)})
                return
            self._write_json(200, schema_structure(schema))

        def do_POST(self) -> None:
            if self.path != "/api/save":
                self._write_json(404, {"errors": [f"no such route: POST {self.path}"]})
                return
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                self._write_json(422, {"errors": [f"malformed JSON body: {exc}"]})
                return
            try:
                schema = schema_from_structure(data)
            except ValidationError as exc:
                self._write_json(422, {"errors": format_validation_errors(exc)})
                return
            save_schema(schema, schema_path)
            self._write_json(200, {"ok": True})

        def log_message(self, format: str, *args: object) -> None:
            pass  # keep CLI output to the greppable URL line, not per-request noise

    return CanvasRequestHandler


def create_server(
    schema_path: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    import_root: Path | None = None,
    scan_dirs: Sequence[Path] = (),
) -> ThreadingHTTPServer:
    """Construct (without running) the canvas API server for SCHEMA_PATH.

    `port=0` (the default) asks the OS for an ephemeral free port. `import_root`
    (default: the current working directory) is where `module:function`
    references resolve from - the same base `loader.resolve_reference` uses at
    compile time, so discovered/previewed references (`FR-4.5`) match what a
    `handler`/`condition`/tool reference would actually import. `scan_dirs`
    optionally restricts which subdirectories `GET /api/callables` walks
    (e.g. to exclude a project's `tests/` directory from suggestions without
    excluding it from real imports) - empty (the default) scans the whole
    `import_root`. Split out from `run_canvas_server` so tests can start/stop
    a real server without going through the CLI's blocking
    `serve_forever`/`KeyboardInterrupt` loop.
    """
    return ThreadingHTTPServer(
        (host, port),
        _handler_for(schema_path, import_root or Path.cwd(), scan_dirs),
    )


def run_canvas_server(
    schema_path: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    scan_dirs: Sequence[Path] = (),
) -> None:
    """Serve SCHEMA_PATH's graph over a local HTTP API until interrupted (FR-4.3)."""
    server = create_server(schema_path, host=host, port=port, scan_dirs=scan_dirs)
    url = f"http://{host}:{server.server_address[1]}"
    print(f"AGENTDRAFT_CANVAS_URL={url}")
    print(f"agentdraft canvas API running at {url}")
    print(f"Point the canvas app at it: cd canvas && VITE_API_BASE={url} npm run dev")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        server.server_close()
