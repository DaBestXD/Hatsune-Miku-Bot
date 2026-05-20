from __future__ import annotations

import unittest
from unittest.mock import patch

from hatsune_miku_bot.botconfig import bot as bot_module


class BotSetupTests(unittest.TestCase):
    def test_botsetup_rejects_missing_discord_token(self) -> None:
        with patch.object(bot_module, "DISCORD_TOKEN", None):
            with self.assertRaisesRegex(ValueError, "Discord token cannot be none"):
                bot_module.botsetup()
