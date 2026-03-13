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
hey start
```

That command starts the full app on `http://127.0.0.1:8000`.

`hey` is the only supported command surface in this repo. It is provided by the shared `agentfoundry` package and reads this repo's local `[tool.agentfoundry]` settings from `pyproject.toml`.

To stop a stale local process that still owns port `8000`:

```bash
hey stop
```

This repo mounts the shared UI through the same FastAPI process, so the app opens directly at `/`.

## Shared Web Development

If you are changing the shared frontend itself, work in `agentfoundry-ui` and point it at this app API with:

```bash
VITE_API_BASE=http://127.0.0.1:8000 npm run dev -- --host 127.0.0.1 --port 3000
```

## Common Commands

- `hey create-agent`
- `hey sync-embedding`
- `hey test`
- `hey format`
- `hey stop`

## Notes

- This repo intentionally keeps only workspace code and the bootstrap needed to run it.
- The shared command surface lives in `agentfoundry` through the `hey` CLI; this repo only supplies local settings in `pyproject.toml`.
- The earlier copied `scripts/` and server files were temporary compatibility scaffolding from the split and do not belong here.
