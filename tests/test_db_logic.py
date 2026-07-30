from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import cast, override
from unittest.mock import AsyncMock, patch

import aiosqlite
from discord import Interaction

from hatsune_miku_bot.audio.song_playlist_classes import Playlist, Song
from hatsune_miku_bot.db_logging import db_main
from hatsune_miku_bot.db_logging.db_main import (
    DBLogic,
    PlaylistSongRemovalStatus,
)


def make_song(title: str, webpage_url: str | None = None) -> Song:
    return Song(
        title,
        webpage_url
        or f"https://example.com/{title.casefold().replace(' ', '-')}",
        None,
        "0",
        "0",
    )


def make_interaction(
    guild_id: int = 1,
    username: str = "Miku",
    user_id: int = 39,
) -> Interaction:
    return cast(
        Interaction,
        SimpleNamespace(
            guild_id=guild_id,
            user=SimpleNamespace(name=username, id=user_id),
        ),
    )


class DBLogicTests(unittest.IsolatedAsyncioTestCase):
    @override
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = Path(self.temp_dir.name) / "playback.sqlite3"
        self.db_path_patch = patch.object(db_main, "DB_PATH", self.db_path)
        self.db_path_patch.start()
        self.addCleanup(self.db_path_patch.stop)
        self.db = await DBLogic.async_init()
        self.addAsyncCleanup(self.db.close)

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

    async def test_async_init_creates_custom_playlist_schema(self) -> None:
        cursor = await self.db.con.execute("PRAGMA table_info(custom_playlist)")

        columns = await cursor.fetchall()

        self.assertEqual(
            [
                (column[1], column[2], column[3], column[5])
                for column in columns
            ],
            [
                ("guild_id", "INTEGER", 1, 1),
                ("playlist_name", "TEXT", 1, 2),
                ("created_by_username", "TEXT", 1, 0),
                ("created_by_user_id", "INTEGER", 1, 0),
                ("created_at", "INTEGER", 1, 0),
            ],
        )

    async def test_async_init_creates_custom_playlist_song_schema(self) -> None:
        cursor = await self.db.con.execute(
            "PRAGMA table_info(custom_playlist_song)"
        )

        columns = await cursor.fetchall()

        self.assertEqual(
            [
                (column[1], column[2], column[3], column[5])
                for column in columns
            ],
            [
                ("guild_id", "INTEGER", 1, 1),
                ("playlist_name", "TEXT", 1, 2),
                ("added_at", "INTEGER", 1, 0),
                ("added_by_id", "INTEGER", 1, 0),
                ("added_by_user", "TEXT", 1, 0),
                ("title", "TEXT", 1, 0),
                ("webpage_url", "TEXT", 1, 3),
                ("thumbnail_url", "TEXT", 0, 0),
                ("duration", "INTEGER", 1, 0),
                ("view_count", "INTEGER", 1, 0),
            ],
        )

    async def test_custom_playlist_song_foreign_keys_are_enabled(self) -> None:
        cursor = await self.db.con.execute("PRAGMA foreign_keys")
        row = await cursor.fetchone()
        assert row is not None
        self.assertEqual(tuple(row), (1,))

        await self.db.con.execute(
            """
            INSERT INTO custom_playlist
                (
                    guild_id,
                    playlist_name,
                    created_by_username,
                    created_by_user_id,
                    created_at
                )
            VALUES (1, 'Miku Mix', 'Miku', 39, 100)
            """
        )
        await self.db.con.execute(
            """
            INSERT INTO custom_playlist_song (
                guild_id,
                playlist_name,
                added_at,
                added_by_id,
                added_by_user,
                title,
                webpage_url,
                thumbnail_url,
                duration,
                view_count
            )
            VALUES (
                1,
                'miku mix',
                101,
                39,
                'Miku',
                'Melt',
                'https://example.com',
                NULL,
                0,
                0
            )
            """
        )
        await self.db.con.execute(
            """
            DELETE FROM custom_playlist
            WHERE guild_id = 1 AND playlist_name = 'MIKU MIX'
            """
        )
        cursor = await self.db.con.execute(
            "SELECT COUNT(*) FROM custom_playlist_song"
        )

        row = await cursor.fetchone()
        assert row is not None
        self.assertEqual(tuple(row), (0,))

    async def test_create_custom_playlist_inserts_timestamped_row(self) -> None:
        with patch.object(db_main.time, "time", return_value=1234567890):
            created = await self.db.create_custom_playlist(
                make_interaction(),
                "Miku Mix",
            )

        cursor = await self.db.con.execute(
            """
            SELECT
                guild_id,
                playlist_name,
                created_by_username,
                created_by_user_id,
                created_at
            FROM custom_playlist
            """
        )

        self.assertTrue(created)
        row = await cursor.fetchone()
        assert row is not None
        self.assertEqual(
            tuple(row),
            (1, "Miku Mix", "Miku", 39, 1234567890),
        )

    async def test_create_custom_playlist_returns_false_for_conflict(
        self,
    ) -> None:
        interaction = make_interaction()

        first_created = await self.db.create_custom_playlist(
            interaction,
            "Miku Mix",
        )
        duplicate_created = await self.db.create_custom_playlist(
            interaction,
            "miku mix",
        )

        self.assertTrue(first_created)
        self.assertFalse(duplicate_created)

    async def test_create_custom_playlist_rolls_back_commit_errors(
        self,
    ) -> None:
        commit_error = aiosqlite.OperationalError("commit failed")
        write_con = aiosqlite.connect(self.db_path)
        rollback = AsyncMock(wraps=write_con.rollback)

        with (
            patch.object(
                db_main.aiosqlite,
                "connect",
                return_value=write_con,
            ),
            patch.object(
                write_con,
                "commit",
                AsyncMock(side_effect=commit_error),
            ),
            patch.object(write_con, "rollback", rollback),
            self.assertRaisesRegex(
                aiosqlite.OperationalError,
                "commit failed",
            ),
        ):
            await self.db.create_custom_playlist(
                make_interaction(),
                "Miku Mix",
            )

        rollback.assert_awaited_once_with()
        cursor = await self.db.con.execute(
            "SELECT COUNT(*) FROM custom_playlist"
        )
        row = await cursor.fetchone()
        assert row is not None
        self.assertEqual(tuple(row), (0,))

    async def test_add_song_to_playlist_inserts_timestamped_row(self) -> None:
        interaction = make_interaction()
        song = Song(
            "Melt",
            "https://song.test/melt",
            "https://image.test/melt.jpg",
            "180",
            "39",
        )
        with patch.object(db_main.time, "time", return_value=100):
            await self.db.create_custom_playlist(interaction, "Miku Mix")

        with patch.object(db_main.time, "time_ns", return_value=101):
            added = await self.db.add_song_to_playlist(
                interaction,
                "Miku Mix",
                song,
            )

        cursor = await self.db.con.execute(
            """
            SELECT
                guild_id,
                playlist_name,
                added_at,
                added_by_id,
                added_by_user,
                title,
                webpage_url,
                thumbnail_url,
                duration,
                view_count
            FROM custom_playlist_song
            """
        )

        self.assertTrue(added)
        row = await cursor.fetchone()
        assert row is not None
        self.assertEqual(
            tuple(row),
            (
                1,
                "Miku Mix",
                101,
                39,
                "Miku",
                "Melt",
                "https://song.test/melt",
                "https://image.test/melt.jpg",
                180,
                39,
            ),
        )

    async def test_add_song_to_playlist_returns_false_for_conflict(
        self,
    ) -> None:
        interaction = make_interaction()
        first_song = make_song("Melt")
        second_song = make_song("World Is Mine", first_song.webpage_url)
        with patch.object(db_main.time, "time", return_value=100):
            await self.db.create_custom_playlist(interaction, "Miku Mix")

        with patch.object(db_main.time, "time", return_value=101):
            first_added = await self.db.add_song_to_playlist(
                interaction,
                "Miku Mix",
                first_song,
            )
            conflicting_added = await self.db.add_song_to_playlist(
                interaction,
                "Miku Mix",
                second_song,
            )

        self.assertTrue(first_added)
        self.assertFalse(conflicting_added)

    async def test_add_song_to_playlist_rejects_missing_webpage_url(
        self,
    ) -> None:
        interaction = make_interaction()
        await self.db.create_custom_playlist(interaction, "Miku Mix")
        song = Song("Melt", None, None, "180", "39")

        added = await self.db.add_song_to_playlist(
            interaction,
            "Miku Mix",
            song,
        )
        cursor = await self.db.con.execute(
            "SELECT COUNT(*) FROM custom_playlist_song"
        )
        row = await cursor.fetchone()

        assert row is not None
        self.assertFalse(added)
        self.assertEqual(tuple(row), (0,))

    async def test_add_song_to_playlist_rolls_back_commit_errors(self) -> None:
        interaction = make_interaction()
        await self.db.create_custom_playlist(interaction, "Miku Mix")
        commit_error = aiosqlite.OperationalError("commit failed")
        write_con = aiosqlite.connect(self.db_path)
        rollback = AsyncMock(wraps=write_con.rollback)

        with (
            patch.object(
                db_main.aiosqlite,
                "connect",
                return_value=write_con,
            ),
            patch.object(
                write_con,
                "commit",
                AsyncMock(side_effect=commit_error),
            ),
            patch.object(write_con, "rollback", rollback),
            self.assertRaisesRegex(
                aiosqlite.OperationalError,
                "commit failed",
            ),
        ):
            await self.db.add_song_to_playlist(
                interaction,
                "Miku Mix",
                make_song("Melt"),
            )

        rollback.assert_awaited_once_with()
        cursor = await self.db.con.execute(
            "SELECT COUNT(*) FROM custom_playlist_song"
        )
        row = await cursor.fetchone()
        assert row is not None
        self.assertEqual(tuple(row), (0,))

    async def test_get_playlist_songs_orders_by_added_at(self) -> None:
        interaction = make_interaction()
        await self.db.create_custom_playlist(interaction, "Miku Mix")
        songs_by_timestamp = [
            (300, make_song("Late")),
            (100, make_song("Early")),
            (200, make_song("Middle")),
        ]
        for timestamp, song in songs_by_timestamp:
            with patch.object(db_main.time, "time_ns", return_value=timestamp):
                await self.db.add_song_to_playlist(
                    interaction,
                    "Miku Mix",
                    song,
                )

        songs = await self.db.get_playlist_songs(
            interaction,
            "miku mix",
        )

        self.assertEqual(
            [song.title for song in songs],
            ["Early", "Middle", "Late"],
        )
        self.assertTrue(all(song.thumbnail_url is None for song in songs))
        cursor = await self.db.con.execute(
            """
            SELECT COUNT(*)
            FROM custom_playlist_song
            WHERE thumbnail_url IS NULL
            """
        )
        row = await cursor.fetchone()
        assert row is not None
        self.assertEqual(tuple(row), (3,))

    async def test_add_playlist_preserves_song_order_with_unique_timestamps(
        self,
    ) -> None:
        interaction = make_interaction()
        await self.db.create_custom_playlist(interaction, "Miku Mix")
        playlist = Playlist(
            [
                make_song("First", "https://song.test/z"),
                make_song("Second", "https://song.test/a"),
                make_song("Third", "https://song.test/m"),
            ]
        )

        with patch.object(db_main.time, "time_ns", return_value=1_000):
            added = await self.db.add_song_to_playlist(
                interaction,
                "Miku Mix",
                playlist,
            )

        cursor = await self.db.con.execute(
            """
            SELECT title, added_at
            FROM custom_playlist_song
            ORDER BY added_at ASC
            """
        )
        rows = await cursor.fetchall()

        self.assertTrue(added)
        self.assertEqual(
            [(row["title"], row["added_at"]) for row in rows],
            [("First", 1_000), ("Second", 1_001), ("Third", 1_002)],
        )

    async def test_remove_song_from_playlist_by_url_returns_title_and_status(
        self,
    ) -> None:
        interaction = make_interaction()
        song = make_song("Melt")
        await self.db.create_custom_playlist(interaction, "Miku Mix")
        await self.db.add_song_to_playlist(
            interaction,
            "Miku Mix",
            song,
        )

        removed = await self.db.remove_song_from_playlist(
            interaction,
            "MIKU MIX",
            song.webpage_url,
        )
        cursor = await self.db.con.execute(
            "SELECT COUNT(*) FROM custom_playlist_song"
        )
        row = await cursor.fetchone()
        assert row is not None
        missing = await self.db.remove_song_from_playlist(
            interaction,
            "Miku Mix",
            song.webpage_url,
        )

        self.assertIs(removed.status, PlaylistSongRemovalStatus.REMOVED)
        self.assertEqual(removed.title, "Melt")
        self.assertEqual(tuple(row), (0,))
        self.assertIs(missing.status, PlaylistSongRemovalStatus.NOT_FOUND)
        self.assertIsNone(missing.title)

    async def test_remove_song_from_playlist_by_unique_title(self) -> None:
        interaction = make_interaction()
        song = make_song("Melt")
        await self.db.create_custom_playlist(interaction, "Miku Mix")
        await self.db.add_song_to_playlist(
            interaction,
            "Miku Mix",
            song,
        )

        removed = await self.db.remove_song_from_playlist(
            interaction,
            "Miku Mix",
            "mElT",
        )

        self.assertIs(removed.status, PlaylistSongRemovalStatus.REMOVED)
        self.assertEqual(removed.title, "Melt")

    async def test_remove_song_from_playlist_rejects_ambiguous_title(
        self,
    ) -> None:
        interaction = make_interaction()
        songs = [
            make_song("Melt", "https://song.test/first"),
            make_song("Melt", "https://song.test/second"),
        ]
        await self.db.create_custom_playlist(interaction, "Miku Mix")
        await self.db.add_song_to_playlist(
            interaction,
            "Miku Mix",
            Playlist(songs),
        )

        result = await self.db.remove_song_from_playlist(
            interaction,
            "Miku Mix",
            "Melt",
        )
        remaining_songs = await self.db.get_playlist_songs(
            interaction,
            "Miku Mix",
        )

        self.assertIs(
            result.status,
            PlaylistSongRemovalStatus.AMBIGUOUS_TITLE,
        )
        self.assertIsNone(result.title)
        self.assertEqual(
            [song.webpage_url for song in remaining_songs],
            [song.webpage_url for song in songs],
        )

    async def test_delete_custom_playlist_cascades_and_reports_missing(
        self,
    ) -> None:
        interaction = make_interaction()
        await self.db.create_custom_playlist(interaction, "Miku Mix")
        await self.db.add_song_to_playlist(
            interaction,
            "Miku Mix",
            make_song("Melt"),
        )

        deleted = await self.db.delete_custom_playlist(
            interaction,
            "miku mix",
        )
        missing_deleted = await self.db.delete_custom_playlist(
            interaction,
            "Miku Mix",
        )
        cursor = await self.db.con.execute(
            "SELECT COUNT(*) FROM custom_playlist_song"
        )

        self.assertTrue(deleted)
        self.assertFalse(missing_deleted)
        row = await cursor.fetchone()
        assert row is not None
        self.assertEqual(tuple(row), (0,))

    async def test_fetch_playlist_names_returns_all_alphabetically_for_guild(
        self,
    ) -> None:
        guild_interaction = make_interaction(guild_id=1)
        other_guild_interaction = make_interaction(guild_id=2)
        for index in reversed(range(30)):
            with patch.object(db_main.time, "time", return_value=index):
                await self.db.create_custom_playlist(
                    guild_interaction,
                    f"Playlist {index:02}",
                )
        with patch.object(db_main.time, "time", return_value=100):
            await self.db.create_custom_playlist(
                other_guild_interaction,
                "Other Guild Playlist",
            )

        playlist_names = await self.db.fetch_playlist_names(guild_interaction)

        self.assertEqual(
            playlist_names,
            [f"Playlist {index:02}" for index in range(30)],
        )

    async def test_fetch_playlist_names_uses_per_guild_cache(self) -> None:
        interaction = make_interaction()
        await self.db.create_custom_playlist(interaction, "Miku Mix")
        first_result = await self.db.fetch_playlist_names(interaction)

        with patch.object(
            self.db.con,
            "execute",
            AsyncMock(side_effect=AssertionError("unexpected database call")),
        ):
            second_result = await self.db.fetch_playlist_names(interaction)

        first_result.append("Caller Mutation")
        self.assertEqual(second_result, ["Miku Mix"])

    async def test_playlist_writes_invalidate_name_cache(self) -> None:
        interaction = make_interaction()
        self.assertEqual(await self.db.fetch_playlist_names(interaction), [])

        await self.db.create_custom_playlist(interaction, "Beta")
        await self.db.create_custom_playlist(interaction, "Alpha")
        self.assertEqual(
            await self.db.fetch_playlist_names(interaction),
            ["Alpha", "Beta"],
        )

        await self.db.delete_custom_playlist(interaction, "Alpha")
        self.assertEqual(
            await self.db.fetch_playlist_names(interaction),
            ["Beta"],
        )

    async def test_fetch_playlist_names_returns_empty_for_unknown_guild(
        self,
    ) -> None:
        self.assertEqual(
            await self.db.fetch_playlist_names(make_interaction(guild_id=404)),
            [],
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
