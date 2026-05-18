from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from hatsune_miku_bot.cogs.musicplayer import MikuMusicCommands


class MikuMusicCommandsTests(unittest.IsolatedAsyncioTestCase):
    async def test_on_guild_remove_stops_and_removes_controller(self) -> None:
        cog = MikuMusicCommands(SimpleNamespace())
        guild = SimpleNamespace(id=42, name="Test Guild")
        controller = SimpleNamespace(stop=AsyncMock())
        cog.guildstate_con_dict[guild.id] = controller

        await cog.on_guild_remove(guild)

        self.assertNotIn(guild.id, cog.guildstate_con_dict)
        controller.stop.assert_awaited_once_with()
