from __future__ import annotations

from agent_foundry.server import create_app
from agent_foundry_ui import mount_ui
from foundry_app.config import default_config


app = create_app(default_config())
mount_ui(app)
