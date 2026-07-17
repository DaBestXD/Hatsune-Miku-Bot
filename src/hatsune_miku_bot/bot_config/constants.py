from __future__ import annotations

import os
from typing import Any, cast

import discord
from dotenv import load_dotenv

from hatsune_miku_bot.bot_config.paths import ENV_PATH, PROJECT_ROOT

load_dotenv(dotenv_path=ENV_PATH)
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
USER_ID = os.getenv("USER_ID")
USER_ID = None if not USER_ID else int(USER_ID)
if GUILD_ID:
    GUILD_OBJECT = discord.Object(id=int(GUILD_ID))
# Any cast to make the type checker shut up cause importing _Params doesnt work😾  # noqa: E501
# Something something private modules something I don't get it yet 🐱
DB_PATH = PROJECT_ROOT / "data" / "status.db"
YDL_OPTS = cast(
    Any,
    {
        "default_search": "ytsearch2",
        "js_runtimes": {"node": {}},
        "extract_flat": "in_playlist",
        "remote_components": ["ejs:github"],
        "quiet": True,
        "extractor_args": {
            "youtube": {"skip": ["hls", "dash", "translated_subs"]}
        },
    },
)
AUDIO_OPTS = cast(
    Any,
    {
        "format": "bestaudio/best",
        "js_runtimes": {"node": {}},
        "default_search": "ytsearch2",
        "remote_components": ["ejs:github"],
        "noplaylist": True,
        "playlist_items": "1-2",
        "quiet": True,
    },
)
SPOTIFY_SEARCH_RESULT_LIMIT = 3
SPOTIFY_SEARCH_OPTS = cast(
    Any,
    {
        "default_search": f"ytsearch{SPOTIFY_SEARCH_RESULT_LIMIT}",
        "js_runtimes": {"node": {}},
        "extract_flat": "in_playlist",
        "remote_components": ["ejs:github"],
        "noplaylist": True,
        "quiet": True,
    },
)
FFMPEG_OPTS = cast(
    Any,
    {
        "before_options": "-nostdin -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",  # noqa: E501
        "options": "-vn -af loudnorm=I=-12:TP=-1.0:LRA=7",
    },
)
SP_PLAYLIST_SONG_METADATA = {
    "market": "US",
    "fields": "items(track(name,duration_ms,artists(name),external_urls(spotify),album(images(url)))),next,total",  # noqa: E501
}
SP_ALBUM_SONG_METADATA = {
    "market": "US",
    "fields": "items(name,duration_ms,artists(name),external_urls(spotify)),next,total",  # noqa: E501
}
SP_PLAYLIST_METADATA = {
    "market": "US",
    "fields": "name,images(url),tracks(total)",
}
SP_ALBUM_METADATA = {
    "market": "US",
    "fields": "name,total_tracks,images(url)",
}
SP_ALBUM_LINK = "https://api.spotify.com/v1/albums/"
SP_TRACK_LINK = "https://api.spotify.com/v1/tracks/"
SP_PLAYLIST_LINK = "https://api.spotify.com/v1/playlists/"
INVIS_CHAR = "\u200b"
DIS_BOT_THUMBNAIL = "attachment://hatsuneplush.jpg"
