from __future__ import annotations

import os
from unittest.mock import patch

import pytest


def pytest_configure(config: pytest.Config) -> None:
    # These values must exist before test modules import application constants.
    # Config cleanup restores the caller's environment even if collection fails.
    environment = patch.dict(
        os.environ,
        {
            "DISCORD_TOKEN": "test-token",
            "GUILD_ID": "1",
            "USER_ID": "1",
            "SPOTIFY_CLIENT_ID": "",
            "SPOTIFY_CLIENT_SECRET": "",
        },
    )
    environment.start()
    config.add_cleanup(environment.stop)
