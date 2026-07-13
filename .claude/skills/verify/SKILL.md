---
name: verify
description: Run this repo's full verification suite (lint, typecheck, tests, coverage gate) for whichever of Python and canvas were touched. Use before considering a change to src/agentdraft or canvas/src complete, or when the user asks to verify/check the build.
---

Run the checks below for whichever stack(s) changed. If both changed, run both. These mirror
`.github/workflows/ci.yml` exactly - if these pass locally, CI should pass.

## Python (`src/agentdraft`, `tests/`)

Run from the repo root:

```
ruff check .
ruff format .
mypy src
pytest tests/unit tests/e2e --cov=agentdraft --cov-report=term-missing
```

- `ruff check .` and `mypy src` (strict mode) must be clean.
- `ruff format .` rewrites files in place - if it changes anything, that's fine, just note it.
- Coverage must stay >= 99% (`fail_under = 99` in `pyproject.toml`). If coverage drops below that,
  the pytest run itself fails - add tests rather than lowering the threshold.

## Canvas (`canvas/`)

Run from `canvas/`:

```
npm run lint
npm run build
npm run test
```

- `npm run lint` runs ESLint (`eslint.config.js`).
- `npm run build` is `tsc -b && vite build` - the typecheck step.
- `npm run test:e2e` (Playwright) requires the Python package to be pip-installed (`pip install
  -e ".[dev]"` from repo root) since the e2e spec spawns a real `agentdraft canvas` process. Only run
  it if asked explicitly or if the change touches the canvas <-> API server contract - it's slower and
  needs `npx playwright install --with-deps chromium` on a fresh machine.

## Reporting

Report pass/fail per command actually run, and any coverage number if it's close to the 99% floor.
Don't silently skip a failing check - surface it even if it looks unrelated to the current change.
