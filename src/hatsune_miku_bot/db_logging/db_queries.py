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
CUSTOM_PLAYLIST_CREATE_QUERY = """
INSERT INTO custom_playlist(
    guild_id,
    playlist_name,
    created_by_username,
    created_by_user_id,
    created_at
)
VALUES (
    :guild_id,
    :playlist_name,
    :created_by_username,
    :created_by_user_id,
    :created_at
)
ON CONFLICT (guild_id, playlist_name) DO NOTHING
RETURNING 1;
"""
CUSTOM_PLAYLIST_ADD_QUERY = """
INSERT INTO custom_playlist_song(
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
    :guild_id,
    :playlist_name,
    :added_at,
    :added_by_id,
    :added_by_user,
    :title,
    :webpage_url,
    :thumbnail_url,
    :duration,
    :view_count
)
ON CONFLICT (guild_id, playlist_name, webpage_url) DO NOTHING;
"""
CUSTOM_PLAYLIST_REMOVE_SONG_QUERY = """
DELETE FROM custom_playlist_song
WHERE rowid = (
    SELECT rowid
    FROM custom_playlist_song
    WHERE guild_id = :guild_id
      AND playlist_name = :playlist_name COLLATE NOCASE
      AND webpage_url = :webpage_url
    ORDER BY added_at ASC
    LIMIT 1
)
RETURNING title;
"""
CUSTOM_PLAYLIST_SONGS_BY_TITLE_QUERY = """
SELECT title, webpage_url
FROM custom_playlist_song
WHERE guild_id = :guild_id
  AND playlist_name = :playlist_name COLLATE NOCASE
  AND title = :title COLLATE NOCASE
ORDER BY added_at ASC;
"""
CUSTOM_PLAYLIST_DELETE_QUERY = """
DELETE FROM custom_playlist
WHERE guild_id = :guild_id
  AND playlist_name = :playlist_name
RETURNING 1;
"""
CUSTOM_PLAYLIST_SONGS_QUERY = """
SELECT
    title,
    webpage_url,
    thumbnail_url,
    duration,
    view_count
FROM custom_playlist_song
WHERE guild_id = :guild_id
  AND playlist_name = :playlist_name COLLATE NOCASE
ORDER BY added_at ASC;
"""
CUSTOM_PLAYLIST_NAMES_QUERY = """
SELECT playlist_name
FROM custom_playlist
WHERE guild_id = :guild_id
ORDER BY playlist_name COLLATE NOCASE ASC, playlist_name ASC;
"""
