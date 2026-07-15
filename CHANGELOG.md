# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/).

The Python package is `agentic-graph-composer` on PyPI, importable as `agc`. The
canvas UI ships bundled inside it - see `docs/ADRs.md` (ADR-015).

## [0.1.0] - 2026-07-16

### Added

- PyPI packaging metadata, `LICENSE` (MIT), and this changelog.
- `agc init` - scaffold a new agent project from a working template.
- `agc doctor` - check the local environment against a schema's
  requirements (API keys, checkpointer DSN, optional extras).
- The canvas UI's prebuilt static assets bundled directly into the Python
  wheel - `agc canvas` now serves both the editing API and the UI
  from one process, with no separate install.
