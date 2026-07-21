from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import override
from unittest.mock import patch

from hatsune_miku_bot.audio.song_playlist_classes import Song
from hatsune_miku_bot.db_logging import db_main
from hatsune_miku_bot.db_logging.db_main import DBLogic


def make_song(title: str) -> Song:
    return Song(title, "https://example.com", "", "0", "0")


class DBLogicTests(unittest.IsolatedAsyncioTestCase):
    @override
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "playback.sqlite3"
        self.db_path_patch = patch.object(db_main, "DB_PATH", self.db_path)
        self.db_path_patch.start()
        self.db = await DBLogic.async_init()

    @override
    async def asyncTearDown(self) -> None:
        await self.db.close()
        self.db_path_patch.stop()
        self.temp_dir.cleanup()

    async def test_async_init_creates_playback_schema(self) -> None:
        cursor = await self.db.con.execute("PRAGMA table_info(song_playback)")

        columns = await cursor.fetchall()

        self.assertEqual(
            [
                (column[1], column[2], column[3], column[5])
                for column in columns
            ],
            [
                ("guild_id", "INTEGER", 1, 1),
                ("song_title", "TEXT", 1, 2),
                ("total_plays", "INTEGER", 1, 0),
                ("last_played_at", "INTEGER", 1, 0),
            ],
        )

    async def test_insert_song_playback_upserts_play_count(self) -> None:
        song = make_song("Melt")

        await self.db.insert_song_playback(song, guild_id=1)
        await self.db.insert_song_playback(song, guild_id=1)

        self.assertEqual(await self.db.rank_song_per_guild(1), [("Melt", 2)])

    async def test_playback_counts_are_isolated_per_guild(self) -> None:
        shared_song = make_song("World Is Mine")
        await self.db.insert_song_playback(shared_song, guild_id=1)
        await self.db.insert_song_playback(shared_song, guild_id=1)
        await self.db.insert_song_playback(shared_song, guild_id=2)
        await self.db.insert_song_playback(make_song("Miku"), guild_id=2)

        self.assertEqual(
            await self.db.rank_song_per_guild(1),
            [("World Is Mine", 2)],
        )
        self.assertEqual(
            await self.db.rank_song_per_guild(2),
            [("Miku", 1), ("World Is Mine", 1)],
        )

    async def test_rankings_order_ties_alphabetically(self) -> None:
        for title in ["Tell Your World", "Melt", "Cendrillon"]:
            await self.db.insert_song_playback(make_song(title), guild_id=1)

        self.assertEqual(
            await self.db.rank_song_per_guild(1),
            [("Cendrillon", 1), ("Melt", 1), ("Tell Your World", 1)],
        )

    async def test_rankings_return_only_top_ten_songs(self) -> None:
        for index in range(12):
            song = make_song(f"Song {index:02}")
            for _ in range(index + 1):
                await self.db.insert_song_playback(song, guild_id=1)

        rankings = await self.db.rank_song_per_guild(1)

        self.assertEqual(len(rankings), 10)
        self.assertEqual(
            rankings,
            [(f"Song {index:02}", index + 1) for index in range(11, 1, -1)],
        )

    async def test_rankings_are_empty_for_guild_without_playback(self) -> None:
        self.assertEqual(await self.db.rank_song_per_guild(404), [])
