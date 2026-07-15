# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Agentic Graph Composer is a CLI- and canvas-first builder for AI agents on LangGraph. Agents are defined as
declarative YAML and compiled into a real LangGraph `StateGraph` (not a reimplementation of LangGraph).

The repo has two parts:
- `src/agc/` - the Python package (CLI, schema, compiler, discovery, local API server for canvas
  editing mode).
- `canvas/` - a standalone React + TypeScript + Vite app (React Flow-based visual editor).

There is no root `README.md`. Design docs live in `docs/` - `docs/README.md` is the docs index,
`docs/PRD.md` is the source of truth for current scope, `docs/ARCHITECTURE.md`, `docs/ADRs.md`, and
`docs/ROADMAP.md` cover design and phasing. `canvas/README.md` covers canvas-specific usage.

## Governing principle

Never build a backend-abstraction or interface (execution-backend interface, backend capability
validation, backend-neutral skills/MCP layer, etc.) until there are two concrete, real consumers that
need it. LangGraph is currently the only backend; a second backend (AgentWeave) is not started. Push
back on feature requests that would add this kind of abstraction prematurely (see ADR-003 in
`docs/ADRs.md`).

## Commands

### Python (root)

- Install: `pip install -e ".[dev]"`
- Lint: `ruff check .`
- Format: `ruff format .`
- Type-check (strict, `src` only): `mypy src`
- Unit tests: `pytest tests/unit`
- E2E tests: `pytest tests/e2e`
- Full suite with coverage gate: `pytest tests/unit tests/e2e --cov=agc --cov-report=term-missing`

Coverage must stay >= 99% (`fail_under = 99` in `pyproject.toml`). New Python code needs
near-complete test coverage or CI fails.

### Canvas (`canvas/`)

- Dev server: `npm run dev`
- Lint: `npm run lint` (ESLint, `eslint.config.js`)
- Build + typecheck: `npm run build` (`tsc -b && vite build`)
- Unit/component tests: `npm run test` (Vitest)
- E2E tests: `npm run test:e2e` (Playwright; spawns a real `agc canvas` process itself, so the
  Python package must be pip-installed first)

## Conventions

- Commit messages: Conventional Commits (`feat:`, `fix:`, `test:`, ...). When a commit closes out a
  specific requirement, append its ID in parentheses, e.g. `feat: provider dropdown for llm nodes
  (FR-4.6)`, `fix: ... (ADR-002)`, or a roadmap phase number like `(2.3)`.
- Commit incrementally per roadmap sub-phase (see `docs/ROADMAP.md`), not as one large commit, unless
  a phase is trivially small.
- LLM API keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.) come from environment variables only -
  never stored in or read from the schema YAML file itself.
- CLI exit codes are a stable contract (see `src/agc/cli.py`): `0` success, `1` validation
  error, `2` compile error, `3` runtime/execution error. Don't change these casually.
- The canvas API server (`agc canvas`) binds to `127.0.0.1` only and has no authentication by
  design (local-first, single-user tool) - this is an accepted trust boundary, not a bug to fix.
- A schema with exactly one node and no `edges` section is valid and implicitly wired
  `START -> node -> END` (see `src/agc/schema.py` module docstring).
