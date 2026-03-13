# Foundry App

Foundry App is the app repo that owns the authored workspace:

- agents
- tools
- skills
- app bootstrap config

The shared runtime and API/server layer live in `agentfoundry`.
The shared packaged UI lives in `agentfoundry-ui`.

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

Both commands start the full app on `http://127.0.0.1:8000`.

To stop a stale local process that still owns port `8000`:

```bash
uv run poe stop
```

This repo mounts the shared UI through the same FastAPI process, so the app opens directly at `/`.

## Shared Web Development

If you are changing the shared frontend itself, work in `agentfoundry-ui` and point it at this app API with:

```bash
VITE_API_BASE=http://127.0.0.1:8000 npm run dev -- --host 127.0.0.1 --port 3000
```

## Common Commands

- `uv run poe new-agent`
- `uv run poe embeddings-sync`
- `uv run poe test`
- `uv run poe format`
- `uv run poe stop`

## Notes

- This repo intentionally keeps only workspace code and the bootstrap needed to run it.
- The earlier copied `scripts/` and server files were temporary compatibility scaffolding from the split and do not belong here.
