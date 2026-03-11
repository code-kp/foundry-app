# Project Overview

This repository is a framework-style agent platform with:

- a stable runtime layer in `src/core/`
- a creator/workspace layer in `src/workspace/`
- a FastAPI backend in `src/server.py`
- a React frontend in `frontend/`

The goal is to keep platform logic separate from agent/tool/skill content while still letting the UI stream live execution events from the runtime.

## Documentation Map

- [README.md](./README.md): local setup, environment, run commands, and day-to-day developer commands
- [src/core/README.md](./src/core/README.md): core runtime architecture and responsibilities
- [src/workspace/README.md](./src/workspace/README.md): how to author agents, tools, and skills in the shared workspace

## Repository Layout

```text
src/
  core/                   platform runtime, discovery, execution, skills, memory
  workspace/              agents, tools, and markdown skills
  api.py                  local API / CLI entrypoint
  server.py               FastAPI server
  services/               backend services such as conversation persistence
frontend/                 React UI
scripts/                  local dev and utility scripts
tests/                    backend test suite
vscode-related-tests/     local VS Code extension source
```

## Core Concepts

### `src/core/`

Owns framework behavior:

- discovery of agents, tools, and skills
- runtime creation and refresh
- direct and orchestrated execution modes
- streaming progress / thinking / assistant events
- skill resolution and memory management

### `src/workspace/`

Owns contributor-authored content:

- `agents/`: agent modules
- `tools/`: shared tool modules
- `skills/`: markdown behavior and knowledge files

## Runtime Shape

At a high level:

1. the platform discovers workspace agents, tools, and skills
2. the selected runtime executes in either `direct` or `orchestrated` mode
3. skills and conversation memory are resolved for the turn
4. tool calls, thinking steps, and assistant output stream back to the UI

## Entry Points

- [`src/server.py`](./src/server.py): HTTP server for the frontend
- [`src/api.py`](./src/api.py): programmatic and CLI interaction entrypoint

## Where To Go Next

- If you need to run the project locally, go back to [README.md](./README.md).
- If you need platform internals, use [src/core/README.md](./src/core/README.md).
- If you need agent/tool/skill authoring guidance, use [src/workspace/README.md](./src/workspace/README.md).
