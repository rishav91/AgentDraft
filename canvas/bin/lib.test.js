import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { configScript, createRequestListener, resolveStaticFile } from "./lib.js";

function makeDistDir() {
  const dir = mkdtempSync(path.join(tmpdir(), "agentdraft-canvas-test-"));
  writeFileSync(path.join(dir, "index.html"), "<html>root</html>");
  mkdirSync(path.join(dir, "assets"));
  writeFileSync(path.join(dir, "assets", "app.js"), "console.log('hi')");
  return dir;
}

function mockReq(url) {
  return { url };
}

function mockRes() {
  return {
    statusCode: null,
    headers: null,
    body: null,
    writeHead(status, headers) {
      this.statusCode = status;
      this.headers = headers;
    },
    end(body) {
      this.body = body;
    },
  };
}

describe("configScript", () => {
  it("emits a script assigning window.__AGENTDRAFT_API_BASE__", () => {
    expect(configScript("http://127.0.0.1:54321")).toBe(
      'window.__AGENTDRAFT_API_BASE__ = "http://127.0.0.1:54321";\n',
    );
  });

  it("JSON-encodes the value so it's safe to embed as a script", () => {
    expect(configScript('http://x/";alert(1);"')).toContain('\\"');
  });
});

describe("resolveStaticFile", () => {
  it("serves index.html for the root path", async () => {
    const file = await resolveStaticFile(makeDistDir(), "/");
    expect(file.body.toString()).toBe("<html>root</html>");
    expect(file.contentType).toContain("text/html");
  });

  it("serves a nested asset with the right content type", async () => {
    const file = await resolveStaticFile(makeDistDir(), "/assets/app.js");
    expect(file.body.toString()).toBe("console.log('hi')");
    expect(file.contentType).toContain("text/javascript");
  });

  it("returns null for a missing file", async () => {
    expect(await resolveStaticFile(makeDistDir(), "/nope.txt")).toBeNull();
  });

  it("refuses to escape distDir via path traversal", async () => {
    expect(await resolveStaticFile(makeDistDir(), "/../../../etc/passwd")).toBeNull();
  });
});

describe("createRequestListener", () => {
  it("serves /agentdraft-config.js with the configured api base", async () => {
    const listener = createRequestListener(makeDistDir(), "http://127.0.0.1:9999");
    const res = mockRes();

    await listener(mockReq("/agentdraft-config.js"), res);

    expect(res.statusCode).toBe(200);
    expect(res.headers["Content-Type"]).toContain("text/javascript");
    expect(res.body).toContain("http://127.0.0.1:9999");
  });

  it("serves a real static asset", async () => {
    const listener = createRequestListener(makeDistDir(), "http://api");
    const res = mockRes();

    await listener(mockReq("/assets/app.js"), res);

    expect(res.statusCode).toBe(200);
    expect(res.body.toString()).toBe("console.log('hi')");
  });

  it("falls back to index.html for an unknown path", async () => {
    const listener = createRequestListener(makeDistDir(), "http://api");
    const res = mockRes();

    await listener(mockReq("/some/deep/path"), res);

    expect(res.statusCode).toBe(200);
    expect(res.body.toString()).toBe("<html>root</html>");
  });

  it("404s when even index.html is missing", async () => {
    const emptyDir = mkdtempSync(path.join(tmpdir(), "agentdraft-canvas-empty-"));
    const listener = createRequestListener(emptyDir, "http://api");
    const res = mockRes();

    await listener(mockReq("/anything"), res);

    expect(res.statusCode).toBe(404);
  });
});
