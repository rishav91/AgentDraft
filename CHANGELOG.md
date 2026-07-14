# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/).

The Python package (`agent-draft` on PyPI, importable as `agentdraft`) and the
canvas frontend (`agentdraft-canvas` on npm) are versioned and released
independently - see `docs/ADRs.md` (ADR-015).

## [Unreleased]

### Added

- PyPI packaging metadata, `LICENSE` (MIT), and this changelog.
- `agentdraft init` - scaffold a new agent project from a working template.
- `agentdraft doctor` - check the local environment against a schema's
  requirements (API keys, checkpointer DSN, optional extras).
- `agentdraft-canvas` npm package with a runtime-configurable API base,
  publishable independently of the Python package.
