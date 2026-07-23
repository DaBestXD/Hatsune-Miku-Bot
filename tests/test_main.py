from __future__ import annotations

import asyncio
import contextlib
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

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
                "--json_logging",
                "--prod_enabled",
            ],
        ):
            result = entrypoint.args()

        self.assertTrue(result.debugger_enabled)
        self.assertTrue(result.json_logging)
        self.assertTrue(result.prod_enabled)


class RunTests(unittest.TestCase):
    def test_run_configures_logging_from_command_flags(self) -> None:
        command_args = SimpleNamespace(
            debugger_enabled=True,
            json_logging=True,
            prod_enabled=True,
        )
        listener = contextlib.nullcontext()

        def close_coroutine(coroutine: object) -> None:
            coroutine.close()  # type: ignore

        run_async = Mock(side_effect=close_coroutine)
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(entrypoint, "args", return_value=command_args),
            patch.object(
                entrypoint,
                "setup_logging",
                return_value=listener,
            ) as setup_logging,
            patch.object(entrypoint.asyncio, "run", run_async),
        ):
            entrypoint.run()

            self.assertEqual(os.environ["APP_ENVIRONMENT"], "PROD")
            self.assertEqual(os.environ["LOG_FORMAT"], "json")

        setup_logging.assert_called_once_with()
        run_async.assert_called_once()


class MainLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_lifecycle_starts_and_closes_bot(
        self,
    ) -> None:
        async def start(token: str) -> None:
            self.assertEqual(token, "token")
            await asyncio.sleep(0)

        bot = FakeBot(start)
        db = SimpleNamespace(close=AsyncMock())

        with (
            patch.object(
                entrypoint, "botsetup", return_value=(bot, "token")
            ) as botsetup,
            patch.object(
                entrypoint.DBLogic,
                "async_init",
                new=AsyncMock(return_value=db),
            ) as db_init,
        ):
            await entrypoint.main(debugger_enabled=True)

        db_init.assert_awaited_once_with()
        botsetup.assert_called_once_with(db, True)
        bot.start.assert_awaited_once_with("token")
        bot.close.assert_awaited_once_with()
        db.close.assert_awaited_once_with()

    async def test_cleanup_runs_when_bot_start_fails(self) -> None:
        bot = FakeBot(RuntimeError("startup failed"))
        db = SimpleNamespace(close=AsyncMock())

        with (
            patch.object(entrypoint, "botsetup", return_value=(bot, "token")),
            patch.object(
                entrypoint.DBLogic,
                "async_init",
                new=AsyncMock(return_value=db),
            ),
            self.assertRaisesRegex(RuntimeError, "startup failed"),
        ):
            await entrypoint.main(debugger_enabled=False)

        bot.close.assert_awaited_once_with()
        db.close.assert_awaited_once_with()
