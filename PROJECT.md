# Project Overview

This repository is the authored app layer for Foundry:

- the workspace in `src/workspace/`
- the app bootstrap in `src/foundry_app/`
- workspace-focused tests in `tests/workspace/`

The shared runtime, API/server layer, web UI, and CLI tooling live in the separate `agentfoundry` repository.

## Documentation Map

- [README.md](./README.md): local setup, environment, run commands, and day-to-day developer commands
- [src/workspace/README.md](./src/workspace/README.md): how to author agents, tools, and skills in this workspace

## Repository Layout

```text
src/
  foundry_app/            app bootstrap and config
  workspace/              agents, tools, and markdown skills
tests/
  workspace/              workspace-specific tests
```

## Repository Boundary

`foundry-app` owns contributor-authored content:

- `agents/`: agent modules
- `tools/`: shared tool modules
- `skills/`: markdown behavior and knowledge files

`agentfoundry` owns reusable platform behavior:

- discovery and runtime creation
- direct and orchestrated execution
- server routes and conversation persistence
- the shared frontend and CLI utilities

## Where To Go Next

- If you need to run the project locally, go back to [README.md](./README.md).
- If you need agent/tool/skill authoring guidance, use [src/workspace/README.md](./src/workspace/README.md).
- If you need platform internals, switch to the `agentfoundry` repository.
