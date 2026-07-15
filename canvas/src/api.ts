import { isGraphStructure, type GraphStructure } from "./types";

export type SaveResult = { ok: true } | { ok: false; errors: string[] };

async function readErrors(response: Response): Promise<string[]> {
  try {
    const body: unknown = await response.json();
    if (
      typeof body === "object" &&
      body !== null &&
      Array.isArray((body as Record<string, unknown>).errors)
    ) {
      return (body as { errors: unknown[] }).errors.map(String);
    }
  } catch {
    // fall through to the generic message below
  }
  return [`request failed with status ${response.status}`];
}

export async function fetchGraph(apiBase: string): Promise<GraphStructure> {
  const response = await fetch(`${apiBase}/api/graph`);
  if (!response.ok) {
    const errors = await readErrors(response);
    throw new Error(errors.join("; "));
  }
  const data: unknown = await response.json();
  if (!isGraphStructure(data)) {
    throw new Error("agc canvas API returned an unexpected shape for /api/graph");
  }
  return data;
}

export async function saveGraph(apiBase: string, structure: GraphStructure): Promise<SaveResult> {
  const response = await fetch(`${apiBase}/api/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(structure),
  });
  if (response.ok) {
    return { ok: true };
  }
  return { ok: false, errors: await readErrors(response) };
}

// Best-effort suggestions for handler/condition/tools fields (FR-4.5) - a
// static scan, so an empty/partial result on failure just means no
// suggestions, not a broken editor. Free-text entry still always works.
export async function fetchCallables(apiBase: string): Promise<string[]> {
  try {
    const response = await fetch(`${apiBase}/api/callables`);
    if (!response.ok) return [];
    const data: unknown = await response.json();
    if (
      typeof data === "object" &&
      data !== null &&
      Array.isArray((data as Record<string, unknown>).callables)
    ) {
      return (data as { callables: unknown[] }).callables.map(String);
    }
    return [];
  } catch {
    return [];
  }
}

// The closed provider list (FR-4.6) - unlike callables, this is a genuinely
// enumerable set (schema.SUPPORTED_PROVIDERS), so an empty result here means
// "fall back to free text", not "no suggestions available".
export async function fetchProviders(apiBase: string): Promise<string[]> {
  try {
    const response = await fetch(`${apiBase}/api/providers`);
    if (!response.ok) return [];
    const data: unknown = await response.json();
    if (
      typeof data === "object" &&
      data !== null &&
      Array.isArray((data as Record<string, unknown>).providers)
    ) {
      return (data as { providers: unknown[] }).providers.map(String);
    }
    return [];
  } catch {
    return [];
  }
}

// Read-only source preview for a discovered callable (FR-4.5) - null means
// "no preview available" (unresolvable ref, network error), never an error
// state to surface, since the field itself still works as free text either way.
export async function fetchCallableSource(apiBase: string, ref: string): Promise<string | null> {
  try {
    const response = await fetch(`${apiBase}/api/source?ref=${encodeURIComponent(ref)}`);
    if (!response.ok) return null;
    const data: unknown = await response.json();
    if (typeof data === "object" && data !== null && typeof (data as Record<string, unknown>).source === "string") {
      return (data as { source: string }).source;
    }
    return null;
  } catch {
    return null;
  }
}

export type SchemaEntry = { path: string; valid: boolean; node_count: number | null };
export type SchemasResult = { active: string | null; schemas: SchemaEntry[] };

// Best-effort, same convention as fetchCallables/fetchProviders (FR-4.7) - an
// empty result just means the sidebar has nothing to show, not a broken editor.
export async function fetchSchemas(apiBase: string): Promise<SchemasResult> {
  try {
    const response = await fetch(`${apiBase}/api/schemas`);
    if (!response.ok) return { active: null, schemas: [] };
    const data: unknown = await response.json();
    if (
      typeof data === "object" &&
      data !== null &&
      typeof (data as Record<string, unknown>).active === "string" &&
      Array.isArray((data as Record<string, unknown>).schemas)
    ) {
      const typed = data as { active: string; schemas: SchemaEntry[] };
      return { active: typed.active, schemas: typed.schemas };
    }
    return { active: null, schemas: [] };
  } catch {
    return { active: null, schemas: [] };
  }
}

export type OpenResult = { ok: true; structure: GraphStructure } | { ok: false; errors: string[] };

// Unlike fetchSchemas, switching the active file is a critical operation
// (FR-4.7) - failures surface as field-specific errors, same convention as
// saveGraph, rather than silently degrading.
export async function openSchema(apiBase: string, path: string): Promise<OpenResult> {
  const response = await fetch(`${apiBase}/api/open`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
  if (!response.ok) {
    return { ok: false, errors: await readErrors(response) };
  }
  const data: unknown = await response.json();
  if (!isGraphStructure(data)) {
    return {
      ok: false,
      errors: ["agc canvas API returned an unexpected shape for /api/open"],
    };
  }
  return { ok: true, structure: data };
}
