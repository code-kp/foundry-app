# Foundry App

Foundry App is the app repo that owns the authored workspace:

- agents
- tools
- skills
- app bootstrap config

The shared runtime, API/server layer, CLI tooling, and shared web UI live in `agentfoundry`.

## Structure

- `src/workspace/`: authored agents, tools, and skills
- `src/foundry_app/`: the minimal app bootstrap and config
- `tests/workspace/`: workspace-only tests

## Install

```bash
uv sync --all-groups --all-extras
```

## Run

```bash
uv run poe backend
```

or

```bash
uv run poe dev
```

Both commands start the app API on `http://127.0.0.1:8000`.

## Shared Web

The shared web lives in `agentfoundry`.

Use the frontend from that repo and point it at this app API with:

```bash
VITE_API_BASE=http://127.0.0.1:8000
```

## Common Commands

- `uv run poe new-agent`
- `uv run poe embeddings-sync`
- `uv run poe test`
- `uv run poe format`

## Notes

- This repo intentionally keeps only workspace code and the bootstrap needed to run it.
- The earlier copied `scripts/` and server files were temporary compatibility scaffolding from the split and do not belong here.
