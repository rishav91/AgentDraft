// Static file server + runtime API-base injection for the published
// agentdraft-canvas npm package (ADR-015). No dependencies - Node's own
// http/fs/path, matching src/agentdraft/server.py's stdlib-only precedent on
// the Python side. Split out from agentdraft-canvas.js so it can be unit
// tested directly, independent of argv parsing and process.exit.

import { readFile, stat } from "node:fs/promises";
import path from "node:path";

const CONTENT_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".png": "image/png",
};

export function configScript(apiBase) {
  return `window.__AGENTDRAFT_API_BASE__ = ${JSON.stringify(apiBase)};\n`;
}

// Resolves URL_PATH to a file under DIST_DIR, refusing to serve anything
// outside it. Returns null if there's no such file (including on traversal
// attempts) so the caller can decide on a fallback.
export async function resolveStaticFile(distDir, urlPath) {
  const distRoot = path.normalize(distDir);
  const relative = urlPath === "/" ? "index.html" : urlPath.replace(/^\/+/, "");
  let filePath = path.normalize(path.join(distRoot, relative));
  if (!filePath.startsWith(distRoot)) {
    return null;
  }

  try {
    const stats = await stat(filePath);
    if (stats.isDirectory()) {
      filePath = path.join(filePath, "index.html");
    }
  } catch {
    return null;
  }

  try {
    const body = await readFile(filePath);
    const contentType = CONTENT_TYPES[path.extname(filePath)] ?? "application/octet-stream";
    return { body, contentType };
  } catch {
    return null;
  }
}

// Builds a Node http request listener serving DIST_DIR's static files, the
// synthetic /agentdraft-config.js route (ADR-015), and an index.html
// fallback for any other unresolved path (this app has no client-side
// routing today, but a direct load/refresh of any path should still work).
export function createRequestListener(distDir, apiBase) {
  return async (req, res) => {
    const urlPath = new URL(req.url, "http://localhost").pathname;

    if (urlPath === "/agentdraft-config.js") {
      res.writeHead(200, { "Content-Type": "text/javascript; charset=utf-8" });
      res.end(configScript(apiBase));
      return;
    }

    const file = (await resolveStaticFile(distDir, urlPath)) ?? (await resolveStaticFile(distDir, "/"));
    if (file === null) {
      res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      res.end("Not found");
      return;
    }
    res.writeHead(200, { "Content-Type": file.contentType });
    res.end(file.body);
  };
}
