import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchCallableSource, fetchCallables } from "./api";

function mockFetch(response: Partial<Response> & { json?: () => Promise<unknown> }) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, status: 200, ...response }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchCallables", () => {
  it("returns the discovered callables on success", async () => {
    mockFetch({ json: () => Promise.resolve({ callables: ["a:b", "c:d"] }) });

    expect(await fetchCallables("http://api")).toEqual(["a:b", "c:d"]);
  });

  it("returns an empty list on a non-ok response", async () => {
    mockFetch({ ok: false, status: 500 });

    expect(await fetchCallables("http://api")).toEqual([]);
  });

  it("returns an empty list on an unexpected response shape", async () => {
    mockFetch({ json: () => Promise.resolve({ nonsense: true }) });

    expect(await fetchCallables("http://api")).toEqual([]);
  });

  it("returns an empty list if the request throws (e.g. network error)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));

    expect(await fetchCallables("http://api")).toEqual([]);
  });
});

describe("fetchCallableSource", () => {
  it("returns the source on success", async () => {
    mockFetch({ json: () => Promise.resolve({ source: "def f(): pass" }) });

    expect(await fetchCallableSource("http://api", "mod:f")).toBe("def f(): pass");
  });

  it("URL-encodes the ref query param", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ source: "x" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await fetchCallableSource("http://api", "pkg.mod:f");

    expect(fetchMock).toHaveBeenCalledWith("http://api/api/source?ref=pkg.mod%3Af");
  });

  it("returns null on a 404 (unresolvable ref)", async () => {
    mockFetch({ ok: false, status: 404 });

    expect(await fetchCallableSource("http://api", "mod:missing")).toBeNull();
  });

  it("returns null if the request throws", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));

    expect(await fetchCallableSource("http://api", "mod:f")).toBeNull();
  });
});
