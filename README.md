# AgentDraft

A CLI- and canvas-first builder for AI agents on LangGraph.
Define an agent as a declarative YAML schema; AgentDraft compiles it into a real LangGraph
`StateGraph` - not a reimplementation of LangGraph, a thin, typed layer on top of it.

[![PyPI](https://img.shields.io/pypi/v/agent-draft)](https://pypi.org/project/agent-draft/)
[![CI](https://github.com/rishav91/AgentDraft/actions/workflows/ci.yml/badge.svg)](https://github.com/rishav91/AgentDraft/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Install

```sh
pip install agent-draft
```

This installs the `agentdraft` command.

## Quickstart

```sh
mkdir my-agent && cd my-agent
agentdraft init                       # scaffolds a working schema.yaml + starter files
cp .env.example .env                  # then fill in your provider's API key
agentdraft validate schema.yaml
agentdraft run schema.yaml "What does this project do?"
```

`agentdraft doctor schema.yaml` checks your environment (API keys, optional extras, checkpointer
config) against what a schema actually needs, before you hit a failure mid-run.

## The canvas (visual editor)

A visual editor for the graph a schema compiles to ships bundled in - no separate install, no
Node.js needed:

```sh
agentdraft canvas schema.yaml
```

This prints a URL - open it in a browser to see and edit the graph, backed by the same
schema/compiler library the CLI uses. See [canvas/README.md](canvas/README.md) for the view-only
mode and running the canvas from source.

## What a schema looks like

```yaml
schema_version: 1
nodes:
  - id: assistant
    llm:
      provider: anthropic
      model: claude-sonnet-5
      system: "You are a helpful assistant."
    tools:
      - tools:search_docs
```

A schema with exactly one node and no `edges` section is implicitly wired `START -> node -> END`.
Multi-node graphs add explicit `edges` (direct or conditional), a `handler` node for custom-code
logic outside the schema, and an opt-in `checkpointer` block for resumable runs.
See [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) for the full setup guide - extras, provider
API keys, Postgres checkpointing, observability.
See [docs/README.md](docs/README.md) for the complete design-doc suite.

## Optional extras

```sh
pip install "agent-draft[examples]"   # langchain-anthropic, langchain-openai - to run examples/
pip install "agent-draft[postgres]"   # Postgres-backed checkpointing
```

## Learn more

- [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) - the practical setup guide
- [docs/README.md](docs/README.md) - architecture, ADRs, requirements, roadmap
- [CONTRIBUTING.md](CONTRIBUTING.md) - developing AgentDraft itself
- [CHANGELOG.md](CHANGELOG.md)

## License

[MIT](LICENSE)
