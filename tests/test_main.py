from __future__ import annotations

import asyncio
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import hatsune_miku_bot.__main__ as entrypoint


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
    async def test_docker_lifecycle_starts_and_closes_bot_and_snapshot(
        self,
    ) -> None:
        snapshot_cancelled = asyncio.Event()

        async def snapshot_loop(_bot: object) -> None:
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                snapshot_cancelled.set()
                raise

        async def start(*, token: str) -> None:
            self.assertEqual(token, "token")
            await asyncio.sleep(0)

        bot = SimpleNamespace(
            start=AsyncMock(side_effect=start),
            close=AsyncMock(),
        )
        command_args = SimpleNamespace(
            docker_enabled=True,
            debugger_enabled=True,
        )

        with (
            patch.object(entrypoint, "db_init", new=AsyncMock()) as db_init,
            patch.object(entrypoint, "args", return_value=command_args),
            patch.object(entrypoint, "logger_config") as logger_config,
            patch.object(
                entrypoint, "botsetup", return_value=(bot, "token")
            ) as botsetup,
            patch.object(
                entrypoint, "snapshot_loop", side_effect=snapshot_loop
            ),
        ):
            await entrypoint.main()

        db_init.assert_awaited_once_with()
        logger_config.assert_called_once_with()
        botsetup.assert_called_once_with(True)
        bot.start.assert_awaited_once_with(token="token")
        bot.close.assert_awaited_once_with()
        self.assertTrue(snapshot_cancelled.is_set())

    async def test_cleanup_runs_when_bot_start_fails(self) -> None:
        async def snapshot_loop(_bot: object) -> None:
            await asyncio.Future()

        bot = SimpleNamespace(
            start=AsyncMock(side_effect=RuntimeError("startup failed")),
            close=AsyncMock(),
        )

        with (
            patch.object(entrypoint, "db_init", new=AsyncMock()),
            patch.object(
                entrypoint,
                "args",
                return_value=SimpleNamespace(
                    docker_enabled=True,
                    debugger_enabled=False,
                ),
            ),
            patch.object(entrypoint, "logger_config"),
            patch.object(entrypoint, "botsetup", return_value=(bot, "token")),
            patch.object(
                entrypoint, "snapshot_loop", side_effect=snapshot_loop
            ),
            self.assertRaisesRegex(RuntimeError, "startup failed"),
        ):
            await entrypoint.main()

        bot.close.assert_awaited_once_with()
