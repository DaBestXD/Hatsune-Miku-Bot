from __future__ import annotations

import asyncio
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import hatsune_miku_bot.__main__ as entrypoint


class FakeBot:
    def __init__(self, start_side_effect: object) -> None:
        self.start = AsyncMock(side_effect=start_side_effect)
        self.close = AsyncMock()

    async def __aenter__(self) -> FakeBot:
        return self

    async def __aexit__(
        self,
        _exc_type: object,
        _exc_value: object,
        _traceback: object,
    ) -> None:
        await self.close()


class ArgumentTests(unittest.TestCase):
    def test_current_enabled_flags_are_parsed(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "hatsune-miku-bot",
                "--debugger_enabled",
            ],
        ):
            result = entrypoint.args()

        self.assertTrue(result.debugger_enabled)


class MainLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_lifecycle_starts_and_closes_bot(
        self,
    ) -> None:
        async def start(token: str) -> None:
            self.assertEqual(token, "token")
            await asyncio.sleep(0)

        bot = FakeBot(start)
        db = SimpleNamespace(close=AsyncMock())
        command_args = SimpleNamespace(debugger_enabled=True)

        with (
            patch.object(entrypoint, "args", return_value=command_args),
            patch.object(entrypoint, "logger_config") as logger_config,
            patch.object(
                entrypoint, "botsetup", return_value=(bot, "token")
            ) as botsetup,
            patch.object(
                entrypoint.DBLogic,
                "async_init",
                new=AsyncMock(return_value=db),
            ) as db_init,
        ):
            await entrypoint.main()

        logger_config.assert_called_once_with()
        db_init.assert_awaited_once_with()
        botsetup.assert_called_once_with(db, True)
        bot.start.assert_awaited_once_with("token")
        bot.close.assert_awaited_once_with()
        db.close.assert_awaited_once_with()

    async def test_cleanup_runs_when_bot_start_fails(self) -> None:
        bot = FakeBot(RuntimeError("startup failed"))
        db = SimpleNamespace(close=AsyncMock())

        with (
            patch.object(
                entrypoint,
                "args",
                return_value=SimpleNamespace(debugger_enabled=False),
            ),
            patch.object(entrypoint, "logger_config"),
            patch.object(entrypoint, "botsetup", return_value=(bot, "token")),
            patch.object(
                entrypoint.DBLogic,
                "async_init",
                new=AsyncMock(return_value=db),
            ),
            self.assertRaisesRegex(RuntimeError, "startup failed"),
        ):
            await entrypoint.main()

        bot.close.assert_awaited_once_with()
        db.close.assert_awaited_once_with()
