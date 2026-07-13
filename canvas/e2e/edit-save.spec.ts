import { expect, test } from "@playwright/test";
import { spawn, spawnSync, type ChildProcessWithoutNullStreams } from "node:child_process";
import { copyFileSync, mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

// End-to-end coverage for Phase 2.2's real edit -> save -> disk round trip
// (ROADMAP 2.3). Drives the actual `agentdraft canvas` server (not a mock),
// against a temp copy of the comprehensive fixture, through a real browser.
// One representative happy path, not an exhaustive suite.

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..", "..");
const FIXTURE = path.join(REPO_ROOT, "tests", "fixtures", "comprehensive.yaml");
const VITE_PORT = 5183;

let apiProcess: ChildProcessWithoutNullStreams;
let viteProcess: ChildProcessWithoutNullStreams;
let apiUrl = "";
let schemaPath = "";

function waitForLine(
  proc: ChildProcessWithoutNullStreams,
  pattern: RegExp,
  timeoutMs = 20_000,
): Promise<RegExpMatchArray> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error(`timed out waiting for ${pattern} on stdout`));
    }, timeoutMs);
    let buffer = "";
    const onData = (chunk: Buffer) => {
      // Strip ANSI escapes: vite/npm color their output whenever FORCE_COLOR
      // leaks into the spawned child's env (Playwright's own runner sets
      // it), which otherwise breaks pattern matching across colored tokens.
      // eslint-disable-next-line no-control-regex
      buffer += chunk.toString().replace(/\x1b\[[0-9;]*m/g, "");
      const match = buffer.match(pattern);
      if (match) {
        clearTimeout(timer);
        proc.stdout.off("data", onData);
        resolve(match);
      }
    };
    proc.stdout.on("data", onData);
  });
}

test.beforeAll(async () => {
  const dir = mkdtempSync(path.join(tmpdir(), "agentdraft-canvas-e2e-"));
  schemaPath = path.join(dir, "schema.yaml");
  copyFileSync(FIXTURE, schemaPath);

  const noColorEnv = { ...process.env, FORCE_COLOR: "0", NO_COLOR: "1" };

  apiProcess = spawn("agentdraft", ["canvas", schemaPath, "--port", "0"], {
    cwd: REPO_ROOT,
    env: { ...noColorEnv, PYTHONUNBUFFERED: "1" },
  });
  const [, url] = await waitForLine(apiProcess, /AGENTDRAFT_CANVAS_URL=(\S+)/);
  apiUrl = url;

  viteProcess = spawn("npm", ["run", "dev", "--", "--port", String(VITE_PORT), "--strictPort"], {
    cwd: path.join(REPO_ROOT, "canvas"),
    env: { ...noColorEnv, VITE_API_BASE: apiUrl },
  });
  await waitForLine(viteProcess, /Local:\s+http:\/\/\S+/);
});

test.afterAll(() => {
  apiProcess?.kill();
  viteProcess?.kill();
});

test("add a node, wire an edge, save, and confirm it persists to disk", async ({ page }) => {
  await page.goto(`http://localhost:${VITE_PORT}`);
  await page.waitForSelector("text=+ Add node");

  await page.click("text=+ Add node");
  await page.waitForSelector(".inspector");
  const idInput = page.locator(".inspector input").first();
  await idInput.fill("responder");
  await idInput.blur();
  await page.fill('.inspector__field:has(label:text("provider")) input', "anthropic");
  await page.fill('.inspector__field:has(label:text("model")) input', "claude-sonnet-5");
  await page.click('button:has-text("+ add direct edge")');

  await page.click('button:has-text("Save")');
  await page.waitForSelector("text=Saved.");

  const saved = readFileSync(schemaPath, "utf-8");
  expect(saved).toContain("id: responder");

  const validate = spawnSync("agentdraft", ["validate", schemaPath], { cwd: REPO_ROOT });
  expect(validate.status).toBe(0);
});
