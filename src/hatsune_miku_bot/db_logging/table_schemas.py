TABLE_CREATION = """
CREATE TABLE IF NOT EXISTS song_playback (
    guild_id       INTEGER NOT NULL,
    song_title     TEXT NOT NULL,
    total_plays    INTEGER NOT NULL DEFAULT 1 CHECK (total_plays >= 1),
    last_played_at INTEGER NOT NULL DEFAULT (unixepoch()),
    PRIMARY KEY (guild_id, song_title)
) STRICT;"""
CUSTOM_PLAYLIST_TABLE_CREATION = """
CREATE TABLE IF NOT EXISTS custom_playlist (
    guild_id            INTEGER NOT NULL,
    playlist_name       TEXT NOT NULL COLLATE NOCASE,
    created_by_username TEXT NOT NULL,
    created_by_user_id  INTEGER NOT NULL,
    created_at          INTEGER NOT NULL,
    PRIMARY KEY (guild_id, playlist_name)
) STRICT;"""
CUSTOM_PLAYLIST_SONG_TABLE_CREATION = """
CREATE TABLE IF NOT EXISTS custom_playlist_song (
    guild_id       INTEGER NOT NULL,
    playlist_name  TEXT NOT NULL COLLATE NOCASE,
    added_at INTEGER NOT NULL DEFAULT (unixepoch()),
    added_by_id INTEGER NOT NULL,
    added_by_user TEXT NOT NULL,
    title          TEXT NOT NULL,
    webpage_url    TEXT NOT NULL,
    thumbnail_url  TEXT,
    duration       INTEGER NOT NULL,
    view_count     INTEGER NOT NULL,
    PRIMARY KEY (guild_id, playlist_name, webpage_url),
    FOREIGN KEY (guild_id, playlist_name)
        REFERENCES custom_playlist (guild_id, playlist_name)
        ON UPDATE CASCADE
        ON DELETE CASCADE
) STRICT;"""
