from __future__ import annotations

import io
import json
import logging
import os
import runpy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, override
from unittest.mock import AsyncMock, call, patch

from discord.app_commands import AppCommandError, CheckFailure

import hatsune_miku_bot.bot_config.client as client_module
import hatsune_miku_bot.bot_config.paths as paths
import hatsune_miku_bot.logging.logging_setup as logging_setup


def as_any(value: object) -> Any:
    return value


class ConstantsAndPathsTests(unittest.TestCase):
    def test_paths_point_to_project_and_packaged_asset_directories(
        self,
    ) -> None:
        self.assertTrue((paths.PROJECT_ROOT / "pyproject.toml").is_file())
        self.assertEqual(paths.PACKAGE_ROOT.name, "hatsune_miku_bot")
        self.assertTrue((paths.ASSET_DIR / "hatsuneplush.jpg").is_file())
        self.assertEqual(paths.ENV_PATH, paths.PROJECT_ROOT / ".env")

    def test_constants_parse_optional_user_id_from_environment(self) -> None:
        constants_path = paths.PACKAGE_ROOT / "bot_config" / "constants.py"
        with (
            patch.dict(
                os.environ,
                {
                    "DISCORD_TOKEN": "test-token",
                    "GUILD_ID": "123",
                    "USER_ID": "456",
                },
                clear=True,
            ),
            patch("dotenv.load_dotenv", autospec=True, return_value=False),
        ):
            loaded = runpy.run_path(str(constants_path))

        self.assertEqual(loaded["DISCORD_TOKEN"], "test-token")
        self.assertEqual(loaded["GUILD_ID"], "123")
        self.assertEqual(loaded["USER_ID"], 456)
        self.assertEqual(loaded["GUILD_OBJECT"].id, 123)


class LoggingConfigTests(unittest.TestCase):
    @override
    def tearDown(self) -> None:
        logging.shutdown()
        logging.getLogger().handlers.clear()

    def test_color_logging_writes_colored_console_and_plain_file(self) -> None:
        console = io.StringIO()
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {"APP_ENVIRONMENT": "DEV", "LOG_FORMAT": "color"},
            ),
            patch.object(logging_setup, "PROJECT_ROOT", Path(directory)),
            patch("sys.stdout", console),
        ):
            listener = logging_setup.setup_logging()
            with listener:
                logging.getLogger("tests.logging").warning(
                    "Color logging test",
                    extra={"event": "color_logging_test"},
                )

            file_output = (Path(directory) / "logs" / "bot.log").read_text()

        self.assertIn("\033[33mWARNING\033[0m", console.getvalue())
        self.assertIn("Color logging test", file_output)
        self.assertNotIn("\033[", file_output)

    def test_json_logging_writes_structured_console_and_file(self) -> None:
        console = io.StringIO()
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {"APP_ENVIRONMENT": "PROD", "LOG_FORMAT": "json"},
            ),
            patch.object(logging_setup, "PROJECT_ROOT", Path(directory)),
            patch("sys.stdout", console),
        ):
            listener = logging_setup.setup_logging()
            with listener:
                logging.getLogger("tests.logging").warning(
                    "JSON logging test",
                    extra={
                        "event": "json_logging_test",
                        "guild_id": 42,
                    },
                )

            file_output = (Path(directory) / "logs" / "bot.log").read_text()

        console_record = json.loads(console.getvalue())
        file_record = json.loads(file_output)
        for record in (console_record, file_record):
            self.assertEqual(record["environment"], "PROD")
            self.assertEqual(record["message"], "JSON logging test")
            self.assertEqual(record["event"], "json_logging_test")
            self.assertEqual(record["guild_id"], 42)


class BotClientTests(unittest.IsolatedAsyncioTestCase):
    def test_botsetup_requires_token_and_forwards_configuration(self) -> None:
        db_logic = as_any(AsyncMock())
        with (
            patch.object(client_module, "DISCORD_TOKEN", None),
            self.assertRaisesRegex(ValueError, "Discord token cannot be none"),
        ):
            client_module.botsetup(db_logic)

        bot = object()
        with (
            patch.object(client_module, "DISCORD_TOKEN", "token"),
            patch.object(client_module, "USER_ID", 39),
            patch.object(client_module, "Bot", return_value=bot) as bot_class,
        ):
            result = client_module.botsetup(db_logic, debugger_on=True)

        self.assertEqual(result, (bot, "token"))
        bot_class.assert_called_once_with(
            owner_id=39,
            db_logic=db_logic,
            debugger_on=True,
        )

    async def test_setup_hook_loads_expected_extensions(self) -> None:
        db_logic = as_any(AsyncMock())
        bot = client_module.Bot(
            owner_id=39,
            db_logic=db_logic,
            debugger_on=True,
        )
        music_cog = as_any(object())

        with (
            patch.object(client_module, "USER_ID", 39),
            patch.object(client_module, "GUILD_ID", "42"),
            patch.object(
                bot, "load_extension", new=AsyncMock()
            ) as load_extension,
            patch.object(bot, "add_cog", new=AsyncMock()) as add_cog,
            patch.object(
                client_module,
                "MikuMusicCommands",
                return_value=music_cog,
            ) as music_cog_class,
            patch.object(bot.tree, "sync", new=AsyncMock()) as sync,
        ):
            await bot.setup_hook()

        self.assertEqual(
            load_extension.await_args_list,
            [
                call("hatsune_miku_bot.cogs.debug"),
                call("hatsune_miku_bot.cogs.utility"),
            ],
        )
        music_cog_class.assert_called_once_with(bot, db_logic)
        add_cog.assert_awaited_once_with(music_cog)
        sync.assert_awaited_once_with()
        await bot.close()

    async def test_app_command_errors_reply_and_record_unexpected_errors(
        self,
    ) -> None:
        bot = client_module.Bot(owner_id=39, db_logic=as_any(AsyncMock()))
        interaction = as_any(SimpleNamespace())

        with (
            patch.object(client_module, "reply", new=AsyncMock()) as reply_mock,
        ):
            await bot.on_app_command_error(interaction, CheckFailure())

            error = AppCommandError("boom")
            await bot.on_app_command_error(interaction, error)
        self.assertEqual(reply_mock.await_count, 2)
        await bot.close()

    async def test_connection_lifecycle_events_are_logged(self) -> None:
        bot = client_module.Bot(owner_id=39, db_logic=as_any(AsyncMock()))

        with self.assertLogs(client_module.logger, level="INFO") as logs:
            await bot.on_disconnect()
            await bot.on_resumed()

        self.assertEqual(
            [record.getMessage() for record in logs.records],
            [
                "Bot disconnected from Discord",
                "Bot reconnected to Discord",
            ],
        )
        await bot.close()
