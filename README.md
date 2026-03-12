# Foundry App

Foundry App is the app repo that owns the authored workspace:

- agents
- tools
- skills
- app bootstrap config

The shared runtime, API factory, and shared web UI live in `agentfoundry`.

## Structure

- `src/workspace/`: authored agents, tools, and skills
- `src/foundry_app/`: app bootstrap and config
- `src/api.py` and `src/server.py`: compatibility entrypoints

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

The app API runs on `http://127.0.0.1:8000`.

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

- This repo is intentionally thinner than the original `agent-hub` repo.
- The first split keeps the authored workspace here and moves the shared platform into `agentfoundry`.
