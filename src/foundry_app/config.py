from __future__ import annotations

from pathlib import Path

from agent_foundry.config import FoundryConfig


def default_config() -> FoundryConfig:
    src_root = Path(__file__).resolve().parents[1]
    return FoundryConfig(
        app_name="Foundry App",
        workspace_root=src_root / "workspace",
        workspace_package="workspace",
        data_root=src_root.parent,
    )
