import { afterEach, describe, expect, it, vi } from "vitest";

import { resolveApiBase } from "./apiBase";

afterEach(() => {
  vi.unstubAllEnvs();
  delete window.__AGC_API_BASE__;
});

describe("resolveApiBase", () => {
  it("prefers VITE_API_BASE (build-time, dev server) when both are set", () => {
    vi.stubEnv("VITE_API_BASE", "http://build-time");
    window.__AGC_API_BASE__ = "http://runtime";

    expect(resolveApiBase()).toBe("http://build-time");
  });

  it("falls back to window.__AGC_API_BASE__ (bundled server, ADR-015) when VITE_API_BASE is unset", () => {
    window.__AGC_API_BASE__ = "http://127.0.0.1:54321";

    expect(resolveApiBase()).toBe("http://127.0.0.1:54321");
  });

  it("treats an empty window.__AGC_API_BASE__ as configured (same origin), not unset", () => {
    window.__AGC_API_BASE__ = "";

    expect(resolveApiBase()).toBe("");
  });

  it("is undefined when neither is set (view-only mode)", () => {
    expect(resolveApiBase()).toBeUndefined();
  });
});
