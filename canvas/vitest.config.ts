import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: true,
    exclude: ["**/node_modules/**", "**/dist/**", "e2e/**"],
    // jsdom 27's css-color dependency is ESM-only; the default "forks" pool
    // loads it via require() and hits ERR_REQUIRE_ESM. "threads" doesn't.
    pool: "threads",
  },
});
