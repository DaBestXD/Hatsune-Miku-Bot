from __future__ import annotations

import importlib
import os
import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock, call, patch

from discord.app_commands import AppCommandError, CheckFailure

import hatsune_miku_bot.bot_config.client as client_module
import hatsune_miku_bot.bot_config.constants as constants
import hatsune_miku_bot.bot_config.logging_config as logging_config
import hatsune_miku_bot.bot_config.paths as paths


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
        original_environment = os.environ.copy()
        try:
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
                patch("dotenv.load_dotenv", return_value=False),
            ):
                reloaded = importlib.reload(constants)
                self.assertEqual(reloaded.DISCORD_TOKEN, "test-token")
                self.assertEqual(reloaded.GUILD_ID, "123")
                self.assertEqual(reloaded.USER_ID, 456)
                self.assertEqual(reloaded.GUILD_OBJECT.id, 123)
        finally:
            os.environ.clear()
            os.environ.update(original_environment)
            importlib.reload(constants)


class LoggingConfigTests(unittest.TestCase):
    def test_logger_config_builds_file_and_console_handlers(self) -> None:
        file_handler = Mock()
        stream_handler = Mock()

        # Directory creation is tested separately from handler wiring to avoid
        # touching the real logs directory.
        fake_log_dir = Mock()
        fake_log_path = Mock()
        fake_log_dir.__truediv__ = Mock(return_value=fake_log_path)
        fake_root = Mock()
        fake_root.__truediv__ = Mock(return_value=fake_log_dir)
        with (
            patch.object(logging_config, "PROJECT_ROOT", fake_root),
            patch.object(
                logging_config,
                "RotatingFileHandler",
                return_value=file_handler,
            ) as rotating_file_handler,
            patch.object(
                logging_config.logging,
                "StreamHandler",
                return_value=stream_handler,
            ),
            patch.object(logging_config.logging, "basicConfig") as basic_config,
            patch.object(
                logging_config.logging, "getLogger", return_value=Mock()
            ),
        ):
            logging_config.logger_config()

        fake_log_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        rotating_file_handler.assert_called_once_with(
            fake_log_path,
            maxBytes=10_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter.assert_called_once()
        stream_handler.setFormatter.assert_called_once()
        basic_config.assert_called_once()


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
