import os
import discord
from typing import cast, Any
from dotenv import load_dotenv
from botextras.loadenv_values import load_env_vals
from botextras.config import ENV_PATH

load_env_vals()
load_dotenv(dotenv_path=ENV_PATH)
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = (os.getenv("GUILD_ID"))
assert GUILD_ID, "Guild ID cannot be none"
assert DISCORD_TOKEN, "Discord token cannot be none"
USER_ID = os.getenv("USER_ID")
USER_ID = None if not USER_ID else int(USER_ID)
GUILD_ID = int(GUILD_ID)
GUILD_OBJECT = discord.Object(id=GUILD_ID)
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
#Any cast to make the type checker shut up cause importing _Params doesnt work😾
#Something something private modules something I don't get it yet 🐱
YDL_OPTS = cast(Any,{
    "format": "bestaudio/best",
    "default_search": "ytsearch2",
    "js_runtimes": {"node": {}},
    "extract_flat": "in_playlist",
    "remote_components": ["ejs:github"],
})
AUDIO_OPTS = cast(Any,{
    "format": "bestaudio/best",
    "js_runtimes": {"node":{}},
    "default_search": "ytsearch1",
    "remote_components": ["ejs:github"],
})
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
