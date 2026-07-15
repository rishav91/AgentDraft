# Contributing to Agentic Graph Composer

## Python (root)

```sh
pip install -e ".[dev]"
ruff check .
ruff format .
mypy src
pytest tests/unit tests/e2e --cov=agc --cov-report=term-missing
```

Coverage must stay >= 99% (`fail_under = 99` in `pyproject.toml`).
New Python code needs near-complete test coverage or CI fails.

## Canvas (`canvas/`)

```sh
cd canvas
npm install
npm run lint
npm run build       # tsc -b && vite build
npm run test        # Vitest
npm run test:e2e    # Playwright - spawns a real `agc canvas` process, so the Python
                     # package must be pip-installed first
```

## Conventions

See [CLAUDE.md](CLAUDE.md) for commit message format, commit granularity, the CLI exit-code
contract, and other repo-wide conventions.
They apply to every contribution, not just Claude Code's own.
