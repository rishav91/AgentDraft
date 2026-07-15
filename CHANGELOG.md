# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/).

The Python package is `agent-draft` on PyPI, importable as `agentdraft`. The
canvas UI ships bundled inside it - see `docs/ADRs.md` (ADR-015).

## [Unreleased]

### Added

- PyPI packaging metadata, `LICENSE` (MIT), and this changelog.
- `agentdraft init` - scaffold a new agent project from a working template.
- `agentdraft doctor` - check the local environment against a schema's
  requirements (API keys, checkpointer DSN, optional extras).
- The canvas UI's prebuilt static assets bundled directly into the Python
  wheel - `agentdraft canvas` now serves both the editing API and the UI
  from one process, with no separate install.
