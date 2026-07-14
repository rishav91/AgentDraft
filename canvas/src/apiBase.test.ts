import { afterEach, describe, expect, it, vi } from "vitest";

import { resolveApiBase } from "./apiBase";

afterEach(() => {
  vi.unstubAllEnvs();
  delete window.__AGENTDRAFT_API_BASE__;
});

describe("resolveApiBase", () => {
  it("prefers VITE_API_BASE (build-time, dev server) when both are set", () => {
    vi.stubEnv("VITE_API_BASE", "http://build-time");
    window.__AGENTDRAFT_API_BASE__ = "http://runtime";

    expect(resolveApiBase()).toBe("http://build-time");
  });

  it("falls back to window.__AGENTDRAFT_API_BASE__ (npm consumer mode) when VITE_API_BASE is unset", () => {
    window.__AGENTDRAFT_API_BASE__ = "http://runtime";

    expect(resolveApiBase()).toBe("http://runtime");
  });

  it("is undefined when neither is set (view-only mode)", () => {
    expect(resolveApiBase()).toBeUndefined();
  });
});
