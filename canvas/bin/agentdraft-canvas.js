#!/usr/bin/env node
// CLI entry point for the published agentdraft-canvas npm package (ADR-015):
// serves the prebuilt dist/ against a running `agentdraft canvas` API.
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { createRequestListener } from "./lib.js";

function parseArgs(argv) {
  let apiBase = null;
  let port = 4173;
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--api-base") {
      apiBase = argv[++i];
    } else if (argv[i] === "--port") {
      port = Number(argv[++i]);
    }
  }
  return { apiBase, port };
}

function main() {
  const { apiBase, port } = parseArgs(process.argv.slice(2));
  if (!apiBase) {
    console.error(
      "error: --api-base is required - pass the URL `agentdraft canvas <schema>` printed, e.g.\n" +
        "  agentdraft canvas schema.yaml\n" +
        "  npx agentdraft-canvas --api-base http://127.0.0.1:54321",
    );
    process.exit(1);
  }

  const distDir = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "dist");
  const server = http.createServer(createRequestListener(distDir, apiBase));
  server.listen(port, () => {
    console.log(`agentdraft-canvas running at http://127.0.0.1:${port} (API: ${apiBase})`);
  });
}

main();
