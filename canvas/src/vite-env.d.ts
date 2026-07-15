/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// Set at runtime by `agentdraft canvas`'s own server (server.py's
// /agentdraft-config.js route, ADR-015) - a fallback for VITE_API_BASE,
// which is build-time-only and unusable for a single prebuilt bundle
// bundled into the Python wheel and served on whatever port that run picks.
interface Window {
  __AGENTDRAFT_API_BASE__?: string;
}
