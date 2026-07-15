"""Local HTTP server backing the canvas's editing session (Phase 2.2, FR-4.3, ADR-008).

Single-user, localhost-only, no auth - the same trust boundary the custom-code
escape hatch already accepts (NFR-4.1, NFR-4.2): the schema author has full local
code execution regardless. Started by `agc canvas <schema>`; stopped with
Ctrl+C.
"""

import json
import mimetypes
from collections.abc import Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import yaml
from pydantic import ValidationError

from agc.compiler import schema_from_structure, schema_structure
from agc.discovery import discover_callables, discover_schema_files, get_callable_source
from agc.schema import (
    SUPPORTED_PROVIDERS,
    format_validation_errors,
    load_schema,
    save_schema,
)

# Bundled canvas UI (ADR-015), populated by hatch_build.py at wheel-build
# time - absent in a source checkout that never ran `npm run build`, or a
# dev install with AGC_SKIP_CANVAS_BUILD set; _resolve_static_file
# degrades to None in that case rather than raising.
_STATIC_DIR = Path(__file__).resolve().parent / "canvas_static"


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _resolve_static_file(url_path: str) -> tuple[bytes, str] | None:
    """Resolve URL_PATH to (body, content_type) under the bundled canvas UI.

    Falls back to index.html for any path with no matching file (this app
    has no client-side routing today, but a direct load/refresh of any path
    should still work) - or refuses to serve anything outside _STATIC_DIR
    (path traversal). Returns None if the canvas UI isn't bundled into this
    install at all, or no fallback index.html exists either.
    """
    if not _STATIC_DIR.is_dir():
        return None

    static_root = _STATIC_DIR.resolve()
    relative = url_path.lstrip("/") or "index.html"
    candidate = (static_root / relative).resolve()
    if not candidate.is_relative_to(static_root) or not candidate.is_file():
        candidate = static_root / "index.html"
    if not candidate.is_file():
        return None

    content_type, _ = mimetypes.guess_type(str(candidate))
    return candidate.read_bytes(), content_type or "application/octet-stream"


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

        def _serve_static_or_config(self, url_path: str) -> None:
            if url_path == "/agc-config.js":
                # Empty string = "same origin" (this server, ADR-015) - the
                # canvas app treats a *configured but empty* value differently
                # from an unset one, so this must never be omitted/undefined.
                body = b'window.__AGC_API_BASE__ = "";\n'
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Type", "text/javascript; charset=utf-8")
                self.end_headers()
                self.wfile.write(body)
                return
            static = _resolve_static_file(url_path)
            if static is None:
                self._write_json(
                    404, {"errors": ["canvas UI is not bundled into this install (ADR-015)"]}
                )
                return
            body, content_type = static
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Type", content_type)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlsplit(self.path)
            if not parsed.path.startswith("/api/"):
                self._serve_static_or_config(parsed.path)
                return
            if parsed.path == "/api/providers":
                self._write_json(200, {"providers": SUPPORTED_PROVIDERS})
                return
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
            if parsed.path == "/api/schemas":
                self._write_json(
                    200,
                    {
                        "active": _relative_path(schema_path, import_root),
                        "schemas": discover_schema_files(import_root, scan_dirs),
                    },
                )
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
            nonlocal schema_path
            if self.path == "/api/open":
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length)
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError as exc:
                    self._write_json(422, {"errors": [f"malformed JSON body: {exc}"]})
                    return
                requested = data.get("path") if isinstance(data, dict) else None
                if not isinstance(requested, str) or not requested:
                    self._write_json(422, {"errors": ["'path' is required"]})
                    return
                candidate = Path(requested)
                if not candidate.is_absolute():
                    candidate = import_root / candidate
                try:
                    schema = load_schema(candidate)
                except FileNotFoundError:
                    self._write_json(404, {"errors": [f"no such file: {requested!r}"]})
                    return
                except yaml.YAMLError as exc:
                    self._write_json(422, {"errors": [f"malformed YAML: {exc}"]})
                    return
                except ValidationError as exc:
                    self._write_json(422, {"errors": format_validation_errors(exc)})
                    return
                schema_path = candidate
                self._write_json(200, schema_structure(schema))
                return
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
    """Serve SCHEMA_PATH's graph over a local HTTP API until interrupted (FR-4.3).

    Also serves the bundled canvas UI (ADR-015) at the same URL, when one was
    bundled into this install - see `_resolve_static_file`.
    """
    server = create_server(schema_path, host=host, port=port, scan_dirs=scan_dirs)
    url = f"http://{host}:{server.server_address[1]}"
    print(f"AGC_CANVAS_URL={url}")
    print(f"agc canvas running at {url} - open it in a browser")
    print(f"(developing the canvas itself? cd canvas && VITE_API_BASE={url} npm run dev)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        server.server_close()
