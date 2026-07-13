import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchCallableSource, fetchCallables, fetchProviders, fetchSchemas, openSchema } from "./api";

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

describe("fetchProviders", () => {
  it("returns the supported provider list on success", async () => {
    mockFetch({ json: () => Promise.resolve({ providers: ["anthropic", "openai"] }) });

    expect(await fetchProviders("http://api")).toEqual(["anthropic", "openai"]);
  });

  it("returns an empty list on a non-ok response", async () => {
    mockFetch({ ok: false, status: 500 });

    expect(await fetchProviders("http://api")).toEqual([]);
  });

  it("returns an empty list on an unexpected response shape", async () => {
    mockFetch({ json: () => Promise.resolve({ nonsense: true }) });

    expect(await fetchProviders("http://api")).toEqual([]);
  });

  it("returns an empty list if the request throws", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));

    expect(await fetchProviders("http://api")).toEqual([]);
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

describe("fetchSchemas", () => {
  it("returns the active path and schema list on success", async () => {
    mockFetch({
      json: () =>
        Promise.resolve({
          active: "schema.yaml",
          schemas: [{ path: "schema.yaml", valid: true, node_count: 2 }],
        }),
    });

    expect(await fetchSchemas("http://api")).toEqual({
      active: "schema.yaml",
      schemas: [{ path: "schema.yaml", valid: true, node_count: 2 }],
    });
  });

  it("returns an empty result on a non-ok response", async () => {
    mockFetch({ ok: false, status: 500 });

    expect(await fetchSchemas("http://api")).toEqual({ active: null, schemas: [] });
  });

  it("returns an empty result on an unexpected response shape", async () => {
    mockFetch({ json: () => Promise.resolve({ nonsense: true }) });

    expect(await fetchSchemas("http://api")).toEqual({ active: null, schemas: [] });
  });

  it("returns an empty result if the request throws", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));

    expect(await fetchSchemas("http://api")).toEqual({ active: null, schemas: [] });
  });
});

describe("openSchema", () => {
  it("returns the new structure on success", async () => {
    mockFetch({
      json: () => Promise.resolve({ schema_version: 1, nodes: [], edges: [] }),
    });

    const result = await openSchema("http://api", "other.yaml");

    expect(result).toEqual({ ok: true, structure: { schema_version: 1, nodes: [], edges: [] } });
  });

  it("posts the path in the request body", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ schema_version: 1, nodes: [], edges: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await openSchema("http://api", "sub/other.yaml");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api/api/open",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ path: "sub/other.yaml" }),
      }),
    );
  });

  it("returns field-specific errors on a non-ok response", async () => {
    mockFetch({ ok: false, status: 422, json: () => Promise.resolve({ errors: ["bad schema"] }) });

    expect(await openSchema("http://api", "bad.yaml")).toEqual({
      ok: false,
      errors: ["bad schema"],
    });
  });

  it("returns an error on an unexpected response shape", async () => {
    mockFetch({ json: () => Promise.resolve({ nonsense: true }) });

    const result = await openSchema("http://api", "other.yaml");

    expect(result.ok).toBe(false);
  });
});
