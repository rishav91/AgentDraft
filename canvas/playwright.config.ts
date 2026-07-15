import { defineConfig } from "@playwright/test";

// No webServer here: the e2e spec spawns the real `agc canvas` API
// process first (to learn its ephemeral port) and only then starts the vite
// dev server with VITE_API_BASE pointed at it - Playwright's built-in
// webServer option can't express that ordering, so the spec manages both
// processes itself (beforeAll/afterAll).
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: {
    headless: true,
  },
});
