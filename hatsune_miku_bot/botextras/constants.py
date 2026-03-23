from __future__ import annotations
import os
import discord
from typing import cast, Any
from dotenv import load_dotenv
from hatsune_miku_bot.botextras.config import ENV_PATH
from pathlib import Path

load_dotenv(dotenv_path=ENV_PATH)
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
assert DISCORD_TOKEN, "Discord token cannot be none"
USER_ID = os.getenv("USER_ID")
USER_ID = None if not USER_ID else int(USER_ID)
if GUILD_ID:
    GUILD_OBJECT = discord.Object(id=int(GUILD_ID))
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
#Any cast to make the type checker shut up cause importing _Params doesnt work😾
#Something something private modules something I don't get it yet 🐱
DB_PATH = Path(__file__).resolve().parents[2] / "data" / "status.db"
YDL_OPTS = cast(Any,{
    "default_search": "ytsearch2",
    "js_runtimes": {"node": {}},
    "extract_flat": "in_playlist",
    "remote_components": ["ejs:github"],
    "quiet" : True,
    "extractor_args": {"youtube": {"skip": ["hls", "dash", "translated_subs"]}},
})
AUDIO_OPTS = cast(Any,{
    "format": "bestaudio/best",
    "js_runtimes": {"node":{}},
    "default_search": "ytsearch2",
    "remote_components": ["ejs:github"],
    "noplaylist" : True,
    "quiet" : True,
})
FFMPEG_OPTS = cast(Any,{
    "before_options": "-nostdin -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn -af loudnorm=I=-12:TP=-1.0:LRA=7",
})
SP_PLAYLIST_PARAMS = {"market": "US","fields": "items(track(name,duration_ms,artists(name),external_urls(spotify),album(images(url)))),next,total",}
SP_ALBUM_PARAMS = {"market": "US","fields": "items(name,duration_ms,artists(name),external_urls(spotify)),next,total",}
SP_PLAYLIST_META_PARAMS = {"market": "US","fields": "name,images(url),tracks(total)",}
SP_ALBUM_META_PARAMS = {"market": "US","fields": "name,total_tracks,images(url)",}
EXTRACT_VALS = ("title", "original_url", "thumbnails", "duration", "view_count")
EXTRACT_AUD_VALS = ("title", "original_url", "thumbnails", "duration", "url")
EXTRACT_VALS_PLAYLIST = ("title", "original_url", "thumbnails")
EXTRACT_VALS_SEARCH = ("title", "url", "thumbnails", "duration", "view_count")
YOUTUBE = "youtu"
SOUNDCLOUD = "soundcloud"
SPOTIFY = "spotify"
SP_ALBUM_LINK = "https://api.spotify.com/v1/albums/"
SP_TRACK_LINK = "https://api.spotify.com/v1/tracks/"
SP_PLAYLIST_LINK = "https://api.spotify.com/v1/playlists/"
INVIS_CHAR = "\u200b"
SLOW_REVERB = ",aecho=0.9:0.8:30|60|90|140:0.55|0.45|0.35|0.25,atempo=0.85"
NIGHTCORE = ",aresample=48000,asetrate=48000*1.25,aresample=48000"
# In seconds
CACHE_TIMER_S = 1800
DIS_BOT_THUMBNAIL = "attachment://hatsuneplush.jpg"
GP_DEBUG_VALUES = {"guild_id","song_cache","songs_list","song_loop","source","volume","text_channel","start_time","seek_time","song_mods","mod_mid_song","nightcore"}
