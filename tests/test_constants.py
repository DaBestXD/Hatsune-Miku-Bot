from __future__ import annotations

import importlib
import os
import sys
import unittest
from unittest.mock import patch


class ConstantsImportTests(unittest.TestCase):
    def test_constants_import_accepts_env_only_configuration(self) -> None:
        original_module = sys.modules.pop("hatsune_miku_bot.botextras.constants", None)
        try:
            with patch.dict(
                os.environ,
                {"DISCORD_TOKEN": "env-token", "GUILD_ID": "1"},
                clear=False,
            ):
                with patch("dotenv.load_dotenv", return_value=False):
                    constants = importlib.import_module(
                        "hatsune_miku_bot.botextras.constants"
                    )
        finally:
            sys.modules.pop("hatsune_miku_bot.botextras.constants", None)
            if original_module is not None:
                sys.modules["hatsune_miku_bot.botextras.constants"] = original_module

        self.assertEqual(constants.DISCORD_TOKEN, "env-token")
        self.assertEqual(constants.GUILD_ID, "1")
