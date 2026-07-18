from typing import Self, TypedDict

import aiosqlite

from hatsune_miku_bot.audio.song_playlist_classes import Song
from hatsune_miku_bot.bot_config.constants import DB_PATH


class _insert_dict(TypedDict):
    guild_id: int
    song_title: str


class DBLogic:
    def __init__(self, con: aiosqlite.Connection) -> None:
        self.con = con

    @classmethod
    async def async_init(cls) -> Self:
        """
        Factory method for creating a db class
        """
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        db = cls(await aiosqlite.connect(DB_PATH))
        await db.con.execute(TABLE_CREATION)
        return db

    async def close(self) -> None:
        await self.con.close()

    async def insert_song_playback(self, song: Song, guild_id: int) -> None:
        args: _insert_dict = {
            "guild_id": guild_id,
            "song_title": song.title,
        }
        await self.con.execute(SONG_INSERT_QUERY, args)
        await self.con.commit()

    async def rank_song_per_guild(self, guild_id: int) -> list[tuple[str, int]]:
        cur = await self.con.execute(SONG_RANKING_QUERY, {"guild_id": guild_id})
        results = await cur.fetchall()
        return [(r[0], r[1]) for r in results]


# TABLE | GUILD_ID(P) | SONG_TITLE(P) | Total_Plays | last_played(utc timestamp)
# TYPES | INT         | INT           | TEXT        | INT
TABLE_CREATION = """
CREATE TABLE IF NOT EXISTS song_playback (
    guild_id       INTEGER NOT NULL,
    song_title     TEXT NOT NULL,
    total_plays    INTEGER NOT NULL DEFAULT 1 CHECK (total_plays >= 1),
    last_played_at INTEGER NOT NULL DEFAULT (unixepoch()),
    PRIMARY KEY (guild_id, song_title)
) STRICT;"""
SONG_INSERT_QUERY = """
INSERT INTO song_playback (guild_id, song_title)
VALUES (:guild_id, :song_title)
ON CONFLICT (guild_id, song_title)
DO UPDATE SET
    total_plays = song_playback.total_plays + 1,
    last_played_at = unixepoch();
"""
SONG_RANKING_QUERY = """
    SELECT song_title, total_plays
    FROM song_playback
    WHERE guild_id = :guild_id
    ORDER BY total_plays DESC, song_title ASC LIMIT 10;
"""
