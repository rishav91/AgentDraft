/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// Set at runtime by the published agentdraft-canvas npm package's server
// (canvas/bin/lib.js's /agentdraft-config.js route, ADR-015) - a fallback for
// VITE_API_BASE, which is build-time-only and unusable for a single prebuilt
// bundle shared by every consumer.
interface Window {
  __AGENTDRAFT_API_BASE__?: string;
}
