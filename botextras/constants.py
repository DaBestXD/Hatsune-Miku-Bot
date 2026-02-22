import os
import discord
from typing import cast, Any
from dotenv import load_dotenv
from botextras.loadenv_values import load_env_vals

load_env_vals()
load_dotenv()
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID")) # pyright: ignore
GUILD_OBJECT = discord.Object(id=GUILD_ID)
USER_ID = int(os.getenv("USER_ID")) # pyright: ignore
#Any cast to make the type checker shut up cause importing _Params doesnt work😾
#Something something private modules something I don't get it yet 🐱
YDL_OPTS = cast(Any,{
    "format": "bestaudio/best",
    "default_search": "ytsearch2",
    "js_runtimes": {"node": {}},
    "extract_flat": "in_playlist",
    "remote_components": ["ejs:github"],
    "quiet" : True})
AUDIO_OPTS = cast(Any,{
    "format": "bestaudio/best",
    "js_runtimes": {"node":{}},
    "default_search": "ytsearch1",
    "remote_components": ["ejs:github"],
    "quiet" : True})
SP_PLAYLIST_PARAMS = {"market": "US","fields": "items(track(name,artists(name),external_urls(spotify))),next,total",}
SP_ALBUM_PARAMS = {"market": "US","fields": "items(name,artists(name),external_urls(spotify)),next,total",}
SP_PLAYLIST_META_PARAMS = {"market": "US","fields": "name,tracks(total)",}
SP_ALBUM_META_PARAMS = {"market": "US","fields": "name,total_tracks",}
YOUTUBE = "youtu"
SOUNDCLOUD = "soundcloud"
SPOTIFY = "spotify"
SP_ALBUM_LINK = "https://api.spotify.com/v1/albums/"
SP_TRACK_LINK = "https://api.spotify.com/v1/tracks/"
SP_PLAYLIST_LINK = "https://api.spotify.com/v1/playlists/"
