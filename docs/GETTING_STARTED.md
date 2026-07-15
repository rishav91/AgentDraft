# Getting Started - Agentic Graph Composer

See [README](README.md) for the doc map.
This is the practical setup guide the root [README](../README.md) defers to - installing, wiring
up env vars, and all three ways to run the canvas.
For *why* things are built this way, see [ARCHITECTURE.md](ARCHITECTURE.md) and [ADRs.md](ADRs.md).

## 1. Install

```sh
pip install agentic-graph-composer
```

This installs the `agc` command (the PyPI distribution name is `agentic-graph-composer`; the import
package and console script are both `agc`).

## 2. Scaffold a project

```sh
mkdir my-agent && cd my-agent
agc init --provider anthropic   # or --provider openai
```

This writes a working `schema.yaml`, its supporting Python module(s) (`tools.py`, and for the
`openai` template also `handlers.py`/`routing.py`), a `NOTES.md` for the bundled `search_docs`
tool to search, a `.env.example`, and a `requirements.txt` (see §5 below).

## 3. Writing tools and handlers

A `tools:` reference is a LangChain tool, built with the standard `@tool` decorator:

```python
from langchain_core.tools import tool

@tool
def search_docs(query: str) -> str:
    """Search this project's docs for lines mentioning `query`."""
    ...
```

The docstring becomes the tool description the LLM sees. A `handler:` node is a plain function
taking/returning the graph's `dict` state, with real LangChain message objects in `messages`:

```python
from langchain_core.messages import AIMessage

def friendly_greeting(state: dict) -> dict:
    return {"messages": [AIMessage(content="Hey there!")]}
```

`examples/tools.py`/`examples/handlers.py` and `agc init`'s generated templates both follow
this pattern - it's the standard, IDE-discoverable way LangChain itself expects tools/messages to
be built, not an Agentic Graph Composer-specific convention.

Since this means your own project imports `langchain_core` directly, pin it to match what your
installed `agentic-graph-composer` version actually requires - check `pip show langchain`'s `Requires-Dist`
line for the `langchain-core` range - rather than leaving it to resolve implicitly, so a future
`agentic-graph-composer` upgrade can't silently shift the `langchain-core` version your imports depend on out
from under you. `agc init`'s generated `requirements.txt` already does this for you (§5).

## 4. Provider API keys

Copy `.env.example` to `.env` and fill in the key your schema's `llm.provider` fields need:

| Provider | Env var |
|---|---|
| `anthropic` | `ANTHROPIC_API_KEY` |
| `openai` | `OPENAI_API_KEY` |

Keys are never stored in or read from the schema YAML file itself - `agc` loads `.env` from
the current directory automatically (`python-dotenv`), but a real exported env var always wins.
Other providers LangChain supports also work; Agentic Graph Composer's own code never reads
`ANTHROPIC_API_KEY`/`OPENAI_API_KEY` directly, LangChain's provider clients do.

Run `agc doctor schema.yaml` at any point to check what's set (presence only - it never
prints a key's value) against what the schema actually needs.

## 5. Optional extras and requirements.txt

```sh
pip install "agentic-graph-composer[examples]"   # langchain-anthropic, langchain-openai - to run examples/
pip install "agentic-graph-composer[postgres]"   # Postgres-backed checkpointing
```

`agc doctor` reports whether a schema needs an extra you haven't installed yet.

`agc init` also generates a `requirements.txt`, pinned to the exact `agentic-graph-composer` and
`langchain-core` versions installed when you scaffolded - the reproducibility half of §3's pinning
advice, done for you. If `agentic-graph-composer` isn't on your package index yet (e.g. you installed it from
a local/vendored wheel), the generated file has a comment showing how to point at that instead.

## 6. Validate and run

```sh
agc validate schema.yaml
agc explain schema.yaml
agc run schema.yaml "What does this project do?"
```

## 7. Checkpointing (resumable runs)

A schema's optional `checkpointer` block makes `agc run` resumable after a crash:

```yaml
checkpointer:
  backend: sqlite   # default - the shared local store, no extra config
```

or, for Postgres:

```yaml
checkpointer:
  backend: postgres
  dsn_env: MY_POSTGRES_DSN   # the env var *name* holding the connection string - never inline it
```

Set `MY_POSTGRES_DSN` (or whatever name the schema's `dsn_env` field uses) in your `.env`, and
install the `postgres` extra above. `agc run schema.yaml --resume <thread_id>` continues an
interrupted run from its last checkpoint.

## 8. Observability

Unset by default - spans are created but exported nowhere. Set the standard OpenTelemetry env
vars to export:

```sh
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
OTEL_SERVICE_NAME=my-agent   # optional, defaults to "agc"
```

See [OBSERVABILITY.md](OBSERVABILITY.md) for what's traced and recommended self-hosted backends to
point OTLP at.

## 9. The canvas (visual editor)

The visual editor ships bundled into `agentic-graph-composer` itself (`ADR-015`) - no separate install, no
Node.js needed:

```sh
agc canvas schema.yaml
```

This prints a URL - open it in a browser. It serves both the editing API and the UI on that one
port, auto-loads `schema.yaml`, and lets you edit nodes/edges/routing and save back to the file.

Two source-only alternatives, for canvas contributors or view-only inspection without any backend:

```sh
# From source, editing mode (fast HMR while developing the UI itself)
agc canvas schema.yaml                              # in one terminal
cd canvas && VITE_API_BASE=<url-it-printed> npm run dev    # in another

# From source, view-only mode (no backend process at all)
agc explain schema.yaml --format json > graph.json
cd canvas && npm run dev
# then load graph.json via the file picker or drag-and-drop
```

See [canvas/README.md](../canvas/README.md) for what each mode renders and edits.

## Troubleshooting

- `agc doctor [schema.yaml]` is the first thing to run when something doesn't work - it
  checks Python version, provider API keys, checkpointer DSN, and optional extras in one pass.
- A validation error names the specific field that's wrong (`agc validate`) rather than a
  generic parse failure - the error message is the fix.
- `agc run --resume <thread_id>` fails fast if the schema changed since that thread's last
  recorded run, to avoid silently resuming against a different compiled graph (`ADR-014`); pass
  `--force` if the change was intentional and safe to resume through.
