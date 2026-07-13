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
    throw new Error("agentdraft canvas API returned an unexpected shape for /api/graph");
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
