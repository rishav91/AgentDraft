# Getting Started - AgentDraft

See [README](README.md) for the doc map.
This is the practical setup guide the root [README](../README.md) defers to - installing, wiring
up env vars, and all three ways to run the canvas.
For *why* things are built this way, see [ARCHITECTURE.md](ARCHITECTURE.md) and [ADRs.md](ADRs.md).

## 1. Install

```sh
pip install agent-draft
```

This installs the `agentdraft` command (the PyPI distribution name is `agent-draft`; the import
package and console script are both `agentdraft`).

## 2. Scaffold a project

```sh
mkdir my-agent && cd my-agent
agentdraft init --provider anthropic   # or --provider openai
```

This writes a working `schema.yaml`, its supporting Python module(s) (`tools.py`, and for the
`openai` template also `handlers.py`/`routing.py`), a `NOTES.md` for the bundled `search_docs`
tool to search, and a `.env.example`.

## 3. Provider API keys

Copy `.env.example` to `.env` and fill in the key your schema's `llm.provider` fields need:

| Provider | Env var |
|---|---|
| `anthropic` | `ANTHROPIC_API_KEY` |
| `openai` | `OPENAI_API_KEY` |

Keys are never stored in or read from the schema YAML file itself - `agentdraft` loads `.env` from
the current directory automatically (`python-dotenv`), but a real exported env var always wins.
Other providers LangChain supports also work; AgentDraft's own code never reads
`ANTHROPIC_API_KEY`/`OPENAI_API_KEY` directly, LangChain's provider clients do.

Run `agentdraft doctor schema.yaml` at any point to check what's set (presence only - it never
prints a key's value) against what the schema actually needs.

## 4. Validate and run

```sh
agentdraft validate schema.yaml
agentdraft explain schema.yaml
agentdraft run schema.yaml "What does this project do?"
```

## 5. Optional extras

```sh
pip install "agent-draft[examples]"   # langchain-anthropic, langchain-openai - to run examples/
pip install "agent-draft[postgres]"   # Postgres-backed checkpointing
```

`agentdraft doctor` reports whether a schema needs an extra you haven't installed yet.

## 6. Checkpointing (resumable runs)

A schema's optional `checkpointer` block makes `agentdraft run` resumable after a crash:

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
install the `postgres` extra above. `agentdraft run schema.yaml --resume <thread_id>` continues an
interrupted run from its last checkpoint.

## 7. Observability

Unset by default - spans are created but exported nowhere. Set the standard OpenTelemetry env
vars to export:

```sh
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
OTEL_SERVICE_NAME=my-agent   # optional, defaults to "agentdraft"
```

See [OBSERVABILITY.md](OBSERVABILITY.md) for what's traced and recommended self-hosted backends to
point OTLP at.

## 8. The canvas (visual editor)

Three ways to run it, from least to most setup:

**a. Published npm package, against a running editing API** (no repo clone needed):

```sh
agentdraft canvas schema.yaml         # starts the local editing API, prints its URL
npx agentdraft-canvas --api-base <url-it-printed>
```

**b. From source, editing mode** (for canvas contributors, or before the npm package exists in
your environment):

```sh
agentdraft canvas schema.yaml                              # in one terminal
cd canvas && VITE_API_BASE=<url-it-printed> npm run dev    # in another
```

**c. From source, view-only mode** (no backend process at all):

```sh
agentdraft explain schema.yaml --format json > graph.json
cd canvas && npm run dev
# then load graph.json via the file picker or drag-and-drop
```

See [canvas/README.md](../canvas/README.md) for what each mode renders and edits.

## Troubleshooting

- `agentdraft doctor [schema.yaml]` is the first thing to run when something doesn't work - it
  checks Python version, provider API keys, checkpointer DSN, and optional extras in one pass.
- A validation error names the specific field that's wrong (`agentdraft validate`) rather than a
  generic parse failure - the error message is the fix.
- `agentdraft run --resume <thread_id>` fails fast if the schema changed since that thread's last
  recorded run, to avoid silently resuming against a different compiled graph (`ADR-014`); pass
  `--force` if the change was intentional and safe to resume through.
