// Build-time (Vite dev server / from-source editing mode) wins over runtime
// (published agentdraft-canvas npm package, ADR-015) when both happen to be set.
export function resolveApiBase(): string | undefined {
  return import.meta.env.VITE_API_BASE ?? window.__AGENTDRAFT_API_BASE__;
}
