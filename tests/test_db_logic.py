from __future__ import annotations

import asyncio
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import hatsune_miku_bot.db_stuff.db_logic as db_logic


class DbLogicTests(unittest.IsolatedAsyncioTestCase):
    async def test_db_init_is_idempotent_and_creates_expected_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "status.db"

            with patch.object(db_logic, "DB_PATH", db_path):
                await db_logic.db_init()
                await db_logic.db_init()

            with sqlite3.connect(db_path) as con:
                tables = {
                    row[0]
                    for row in con.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }

        self.assertIn("events", tables)
        self.assertIn("snapshots", tables)

    async def test_snapshot_loop_writes_a_valid_snapshot_row(self) -> None:
        real_sleep = asyncio.sleep

        async def cancel_after_first_sleep(_delay: float) -> None:
            raise asyncio.CancelledError

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "status.db"
            bot = SimpleNamespace(
                latency=0.123,
                process_start=datetime.now(timezone.utc) - timedelta(seconds=12),
                is_ready=lambda: True,
            )

            with patch.object(db_logic, "DB_PATH", db_path):
                await db_logic.db_init()
                with patch.object(db_logic.asyncio, "sleep", side_effect=cancel_after_first_sleep):
                    with self.assertRaises(asyncio.CancelledError):
                        await db_logic.snapshot_loop(bot)

            with sqlite3.connect(db_path) as con:
                row = con.execute(
                    """
                    SELECT status, discord_connection, latency_ms, uptime_seconds
                    FROM snapshots
                    """
                ).fetchone()

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row[0], "online")
        self.assertEqual(row[1], 1)
        self.assertAlmostEqual(row[2], 123.0, places=2)
        self.assertGreaterEqual(row[3], 12)

    async def test_snapshot_loop_continues_after_insert_failure(self) -> None:
        real_sleep = asyncio.sleep
        insert_calls: list[dict[str, object]] = []
        second_attempt_reached = asyncio.Event()

        async def fake_insert_snapshot(**kwargs):
            insert_calls.append(kwargs)
            if len(insert_calls) == 1:
                raise RuntimeError("sqlite busy")
            second_attempt_reached.set()

        async def fast_sleep(_delay: float) -> None:
            await real_sleep(0)

        bot = SimpleNamespace(
            latency=0.05,
            process_start=datetime.now(timezone.utc) - timedelta(seconds=5),
            is_ready=lambda: True,
        )

        with (
            patch.object(db_logic, "insert_snapshot", side_effect=fake_insert_snapshot),
            patch.object(db_logic.asyncio, "sleep", side_effect=fast_sleep),
        ):
            task = asyncio.create_task(db_logic.snapshot_loop(bot))
            await asyncio.wait_for(second_attempt_reached.wait(), timeout=1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        self.assertEqual(len(insert_calls), 2)
        self.assertEqual(insert_calls[0]["status"], "online")
        self.assertEqual(insert_calls[1]["discord_connection"], 1)
