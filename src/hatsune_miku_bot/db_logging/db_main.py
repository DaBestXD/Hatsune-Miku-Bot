import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from enum import StrEnum
from pathlib import Path
from sqlite3 import Row
from typing import NamedTuple, NotRequired, Self, TypedDict

import aiosqlite
from discord import Interaction

from hatsune_miku_bot.audio.song_playlist_classes import Playlist, Song
from hatsune_miku_bot.bot_config.constants import DB_PATH
from hatsune_miku_bot.db_logging.db_queries import (
    CUSTOM_PLAYLIST_ADD_QUERY,
    CUSTOM_PLAYLIST_CREATE_QUERY,
    CUSTOM_PLAYLIST_DELETE_QUERY,
    CUSTOM_PLAYLIST_NAMES_QUERY,
    CUSTOM_PLAYLIST_REMOVE_SONG_QUERY,
    CUSTOM_PLAYLIST_SONGS_BY_TITLE_QUERY,
    CUSTOM_PLAYLIST_SONGS_QUERY,
    SONG_INSERT_QUERY,
    SONG_RANKING_QUERY,
)
from hatsune_miku_bot.db_logging.table_schemas import (
    CUSTOM_PLAYLIST_SONG_TABLE_CREATION,
    CUSTOM_PLAYLIST_TABLE_CREATION,
    TABLE_CREATION,
)
from hatsune_miku_bot.utils.discord_helpers import _is_http_url


class SongInsertDict(TypedDict):
    guild_id: int
    song_title: str


class PlaylistCreationDict(TypedDict):
    guild_id: int
    playlist_name: str
    created_by_username: str
    created_by_user_id: int
    created_at: int


class PlaylistSongInsertDict(TypedDict):
    guild_id: int
    playlist_name: str
    added_at: int
    added_by_id: int
    added_by_user: str
    title: str
    webpage_url: str
    thumbnail_url: str | None
    duration: int
    view_count: int


class PlaylistLookupDict(TypedDict):
    guild_id: int
    playlist_name: str
    title: NotRequired[str]
    webpage_url: NotRequired[str]


class PlaylistSongsCacheKey(NamedTuple):
    guild_id: int
    playlist_name: str


class PlaylistSongRemovalStatus(StrEnum):
    REMOVED = "removed"
    NOT_FOUND = "not_found"
    AMBIGUOUS_TITLE = "ambiguous_title"


class PlaylistSongRemovalResult(NamedTuple):
    status: PlaylistSongRemovalStatus
    title: str | None = None


# TODO: add logging


class DBLogic:
    def __init__(self, con: aiosqlite.Connection, db_path: Path) -> None:
        self.con = con
        self.db_path = db_path
        self._playlist_names_cache: dict[int, tuple[str, ...]] = {}
        """
        Dict of key of guild_id:
        Value of playlist names
        """
        self._playlist_songs_cache: dict[
            PlaylistSongsCacheKey, tuple[Song, ...]
        ] = {}

    @classmethod
    async def async_init(cls) -> Self:
        """
        Factory method for creating a db class
        """
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        db = cls(await aiosqlite.connect(DB_PATH), DB_PATH)
        db.con.row_factory = Row
        await db.con.execute("PRAGMA foreign_keys = ON")
        await db.con.execute(TABLE_CREATION)
        await db.con.execute(CUSTOM_PLAYLIST_TABLE_CREATION)
        await db.con.execute(CUSTOM_PLAYLIST_SONG_TABLE_CREATION)
        await db.con.commit()
        return db

    async def close(self) -> None:
        self._playlist_names_cache.clear()
        self._playlist_songs_cache.clear()
        await self.con.close()

    def invalidate_playlist_names_cache(self, guild_id: int) -> None:
        self._playlist_names_cache.pop(guild_id, None)

    def invalidate_playlist_songs_cache(self, guild_id: int) -> None:
        keys_to_remove = [
            key
            for key in self._playlist_songs_cache
            if key.guild_id == guild_id
        ]
        for key in keys_to_remove:
            self._playlist_songs_cache.pop(key, None)

    @staticmethod
    def song_from_data(data: Row) -> Song:
        return Song(
            title=data["title"],
            webpage_url=data["webpage_url"],
            thumbnail_url=data["thumbnail_url"] or None,
            duration=str(data["duration"]),
            view_count=str(data["view_count"]),
        )

    @asynccontextmanager
    async def _write_transaction(
        self,
    ) -> AsyncIterator[aiosqlite.Connection]:
        async with aiosqlite.connect(self.db_path) as con:
            con.row_factory = Row
            await con.execute("PRAGMA foreign_keys = ON")
            try:
                yield con
                await con.commit()
            except BaseException:
                await con.rollback()
                raise

    async def insert_song_playback(self, song: Song, guild_id: int) -> None:
        args: SongInsertDict = {
            "guild_id": guild_id,
            "song_title": song.title,
        }
        async with self._write_transaction() as con:
            await con.execute(SONG_INSERT_QUERY, args)

    async def rank_song_per_guild(self, guild_id: int) -> list[tuple[str, int]]:
        cur = await self.con.execute(SONG_RANKING_QUERY, {"guild_id": guild_id})
        results = await cur.fetchall()
        return [(r["song_title"], r["total_plays"]) for r in results]

    async def create_custom_playlist(
        self, interaction: Interaction, playlist_name: str
    ) -> bool:
        args: PlaylistCreationDict = {
            "guild_id": interaction.guild_id or 0,
            "playlist_name": playlist_name,
            "created_by_username": interaction.user.name,
            "created_by_user_id": interaction.user.id,
            "created_at": int(time.time()),
        }
        async with self._write_transaction() as con:
            cursor = await con.execute(
                CUSTOM_PLAYLIST_CREATE_QUERY,
                args,
            )
            created = await cursor.fetchone() is not None
        if created:
            self.invalidate_playlist_names_cache(args["guild_id"])
        return created

    async def add_song_to_playlist(
        self,
        interaction: Interaction,
        playlist_name: str,
        song_object: Song | Playlist,
    ) -> bool:
        guild_id = interaction.guild_id or 0
        result = (
            song_object.songs
            if isinstance(song_object, Playlist)
            else [song_object]
        )
        added_at = time.time_ns()
        args: list[PlaylistSongInsertDict] = []
        for s in result:
            if not s.webpage_url:
                continue
            args.append(
                {
                    "guild_id": guild_id,
                    "playlist_name": playlist_name,
                    "added_at": added_at + len(args),
                    "added_by_id": interaction.user.id,
                    "added_by_user": interaction.user.name,
                    "title": s.title,
                    "webpage_url": s.webpage_url,
                    "thumbnail_url": s.thumbnail_url,
                    "duration": s.duration,
                    "view_count": (
                        int(s.view_count) if s.view_count.isnumeric() else 0
                    ),
                }
            )
        async with self._write_transaction() as con:
            cursor = await con.executemany(
                CUSTOM_PLAYLIST_ADD_QUERY,
                args,
            )
            added = cursor.rowcount > 0
        if added:
            self.invalidate_playlist_songs_cache(guild_id)
        return added

    async def remove_song_from_playlist(
        self,
        interaction: Interaction,
        playlist_name: str,
        song_identifier: str | None,
    ) -> PlaylistSongRemovalResult:
        if not song_identifier:
            return PlaylistSongRemovalResult(
                PlaylistSongRemovalStatus.NOT_FOUND
            )
        args: PlaylistLookupDict = {
            "guild_id": interaction.guild_id or 0,
            "playlist_name": playlist_name,
        }
        async with self._write_transaction() as con:
            if _is_http_url(song_identifier):
                args["webpage_url"] = song_identifier
            else:
                args["title"] = song_identifier
                cursor = await con.execute(
                    CUSTOM_PLAYLIST_SONGS_BY_TITLE_QUERY,
                    args,
                )
                matching_songs = list(await cursor.fetchall())
                if not matching_songs:
                    return PlaylistSongRemovalResult(
                        PlaylistSongRemovalStatus.NOT_FOUND
                    )
                if len(matching_songs) > 1:
                    return PlaylistSongRemovalResult(
                        PlaylistSongRemovalStatus.AMBIGUOUS_TITLE
                    )
                args["webpage_url"] = matching_songs[0]["webpage_url"]

            cursor = await con.execute(
                CUSTOM_PLAYLIST_REMOVE_SONG_QUERY,
                args,
            )
            removed_row = await cursor.fetchone()
        if removed_row is None:
            return PlaylistSongRemovalResult(
                PlaylistSongRemovalStatus.NOT_FOUND
            )
        self.invalidate_playlist_songs_cache(args["guild_id"])
        return PlaylistSongRemovalResult(
            PlaylistSongRemovalStatus.REMOVED,
            removed_row["title"],
        )

    async def delete_custom_playlist(
        self,
        interaction: Interaction,
        playlist_name: str,
    ) -> bool:
        args: PlaylistLookupDict = {
            "guild_id": interaction.guild_id or 0,
            "playlist_name": playlist_name,
        }
        async with self._write_transaction() as con:
            cursor = await con.execute(
                CUSTOM_PLAYLIST_DELETE_QUERY,
                args,
            )
            deleted = await cursor.fetchone() is not None
        if deleted:
            self.invalidate_playlist_names_cache(args["guild_id"])
            self.invalidate_playlist_songs_cache(args["guild_id"])
        return deleted

    async def get_playlist_songs(
        self,
        interaction: Interaction,
        playlist_name: str,
    ) -> list[Song]:
        guild_id = interaction.guild_id or 0
        cache_key = PlaylistSongsCacheKey(guild_id, playlist_name)
        cached_songs = self._playlist_songs_cache.get(cache_key)
        if cached_songs is not None:
            return list(cached_songs)

        args: PlaylistLookupDict = {
            "guild_id": guild_id,
            "playlist_name": playlist_name,
        }
        cursor = await self.con.execute(
            CUSTOM_PLAYLIST_SONGS_QUERY,
            args,
        )
        rows = await cursor.fetchall()
        songs = tuple(self.song_from_data(row) for row in rows)
        self._playlist_songs_cache[cache_key] = songs
        return list(songs)

    async def fetch_playlist_names(self, interaction: Interaction) -> list[str]:
        guild_id = interaction.guild_id or 0
        cached_names = self._playlist_names_cache.get(guild_id)
        if cached_names is not None:
            return list(cached_names)

        args: dict[str, int] = {
            "guild_id": guild_id,
        }
        cursor = await self.con.execute(
            CUSTOM_PLAYLIST_NAMES_QUERY,
            args,
        )
        rows = await cursor.fetchall()
        playlist_names = tuple(row["playlist_name"] for row in rows)
        self._playlist_names_cache[guild_id] = playlist_names
        return list(playlist_names)
