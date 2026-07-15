// Prefers build-time VITE_API_BASE (the from-source dev-server workflow,
// still used by canvas contributors iterating on the UI against a real
// `agentdraft canvas` instance on a different port) over the runtime value
// `agentdraft canvas`'s own server injects via /agentdraft-config.js
// (ADR-015). That injected value is "" for "same origin as this server" -
// a real, meaningful configuration, not an absence of one - so this checks
// `!== undefined` rather than truthiness; a plain `??`/truthy check would
// incorrectly treat "" as unset and fall back to view-only mode.
export function resolveApiBase(): string | undefined {
  if (import.meta.env.VITE_API_BASE !== undefined) {
    return import.meta.env.VITE_API_BASE;
  }
  return window.__AGENTDRAFT_API_BASE__;
}
