from __future__ import annotations

from agent_foundry.api import AgentApi, ChatResult, _parse_sse_frame, create_runtime
from foundry_app.config import default_config


service, api = create_runtime(default_config())


def main() -> int:
    from agent_foundry.api import main as foundry_main

    return foundry_main(config=default_config())


__all__ = [
    "AgentApi",
    "ChatResult",
    "_parse_sse_frame",
    "api",
    "main",
    "service",
]


if __name__ == "__main__":
    raise SystemExit(main())
