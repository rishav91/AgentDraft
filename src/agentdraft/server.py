"""Local HTTP server backing the canvas's editing session (Phase 2.2, FR-4.3, ADR-008).

Single-user, localhost-only, no auth - the same trust boundary the custom-code
escape hatch already accepts (NFR-4.1, NFR-4.2): the schema author has full local
code execution regardless. Started by `agentdraft canvas <schema>`; stopped with
Ctrl+C.
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from pydantic import ValidationError

from agentdraft.compiler import schema_from_structure, schema_structure
from agentdraft.discovery import discover_callables, get_callable_source
from agentdraft.schema import format_validation_errors, load_schema, save_schema


def _handler_for(schema_path: Path, scan_root: Path) -> type[BaseHTTPRequestHandler]:
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
                self._write_json(200, {"callables": discover_callables(scan_root)})
                return
            if parsed.path == "/api/source":
                ref = parse_qs(parsed.query).get("ref", [""])[0]
                source = get_callable_source(scan_root, ref)
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
    scan_root: Path | None = None,
) -> ThreadingHTTPServer:
    """Construct (without running) the canvas API server for SCHEMA_PATH.

    `port=0` (the default) asks the OS for an ephemeral free port. `scan_root`
    (default: the current working directory) is where `GET /api/callables`
    (`FR-4.5`) looks for `module:function` references - the same base modules
    resolve against at runtime (`loader.resolve_reference`), so results match
    what a `handler`/`condition`/tool reference would actually import. Split
    out from `run_canvas_server` so tests can start/stop a real server without
    going through the CLI's blocking `serve_forever`/`KeyboardInterrupt` loop.
    """
    return ThreadingHTTPServer(
        (host, port), _handler_for(schema_path, scan_root or Path.cwd())
    )


def run_canvas_server(schema_path: Path, *, host: str = "127.0.0.1", port: int = 0) -> None:
    """Serve SCHEMA_PATH's graph over a local HTTP API until interrupted (FR-4.3)."""
    server = create_server(schema_path, host=host, port=port)
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
