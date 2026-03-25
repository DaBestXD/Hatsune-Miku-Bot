from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import hatsune_miku_bot.main as main


class MainLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_main_loads_env_and_cleans_up_snapshot_task(self) -> None:
        snapshot_cancelled = asyncio.Event()

        async def fake_snapshot_loop(_bot) -> None:
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                snapshot_cancelled.set()
                raise

        async def fake_start(*, token: str) -> None:
            await asyncio.sleep(0)

        bot = SimpleNamespace(
            start=AsyncMock(side_effect=fake_start),
            close=AsyncMock(),
        )

        with (
            patch.object(main, "db_init", AsyncMock()) as db_init_mock,
            patch.object(
                main.argparse.ArgumentParser,
                "parse_args",
                return_value=SimpleNamespace(docker=False, debugger=False),
            ),
            patch.object(main, "load_env_vals") as load_env_vals_mock,
            patch.object(main, "logger_config") as logger_config_mock,
            patch.object(main, "botsetup", return_value=(bot, "token")) as botsetup_mock,
            patch.object(main, "snapshot_loop", side_effect=fake_snapshot_loop),
        ):
            await main.main()

        db_init_mock.assert_awaited_once_with()
        load_env_vals_mock.assert_called_once_with()
        logger_config_mock.assert_called_once_with()
        botsetup_mock.assert_called_once_with(False)
        bot.start.assert_awaited_once_with(token="token")
        bot.close.assert_awaited_once_with()
        self.assertTrue(snapshot_cancelled.is_set())

    async def test_main_skips_env_load_for_docker_and_still_closes_on_error(self) -> None:
        snapshot_cancelled = asyncio.Event()

        async def fake_snapshot_loop(_bot) -> None:
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                snapshot_cancelled.set()
                raise

        async def failing_start(*, token: str) -> None:
            await asyncio.sleep(0)
            raise RuntimeError("startup failed")

        bot = SimpleNamespace(
            start=AsyncMock(side_effect=failing_start),
            close=AsyncMock(),
        )

        with (
            patch.object(main, "db_init", AsyncMock()) as db_init_mock,
            patch.object(
                main.argparse.ArgumentParser,
                "parse_args",
                return_value=SimpleNamespace(docker=True, debugger=True),
            ),
            patch.object(main, "load_env_vals") as load_env_vals_mock,
            patch.object(main, "logger_config") as logger_config_mock,
            patch.object(main, "botsetup", return_value=(bot, "token")) as botsetup_mock,
            patch.object(main, "snapshot_loop", side_effect=fake_snapshot_loop),
        ):
            with self.assertRaises(RuntimeError):
                await main.main()

        db_init_mock.assert_awaited_once_with()
        load_env_vals_mock.assert_not_called()
        logger_config_mock.assert_called_once_with()
        botsetup_mock.assert_called_once_with(True)
        bot.start.assert_awaited_once_with(token="token")
        bot.close.assert_awaited_once_with()
        self.assertTrue(snapshot_cancelled.is_set())
