import random
import time
import os
from typing import Any
from yt_dlp.utils import DownloadError
from hatsune_miku_bot.botextras.constants import YDL_OPTS
from yt_dlp import YoutubeDL
import asyncio
import logging
import aiohttp
import base64
from hatsune_miku_bot.audio_utils.audio_class import Song, Playlist

logger = logging.getLogger(__name__)


# FOR CODEX NOTES:
# - Goal of refactor to move away from requests and removal from dependacies
# - and to try to reduce blocking calls as much as possible
class Spotify:
    def __init__(self, client: aiohttp.ClientSession):
        self.client_id = os.getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        self.token: str | None = None
        self.token_expiry: float = -1
        self.client = client

    async def get_token(self, max_attempts: int = 3) -> None:
        if not self.client_id or not self.client_secret:
            logger.warning("Attempted to play spotify song without credentials")
            return None
        if self.token and time.time() < self.token_expiry:
            logger.debug(
                "Token already cached, token expiry at %d", int(self.token_expiry)
            )
            return None
        if max_attempts <= 0:
            return None
        auth_string = f"{self.client_id}:{self.client_secret}".encode("utf-8")
        url = "https://accounts.spotify.com/api/token"
        auth_base64 = str(base64.b64encode(auth_string))
        headers = {
            "Authorization": f"Basic {auth_base64}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"grant_type": "client_credentials"}
        try:
            async with self.client.post(
                url,
                headers=headers,
                data=data,
            ) as res:
                res.raise_for_status()
                token_response = await res.json()
                if not isinstance(token_response, dict):
                    # This should never happened
                    logger.error(
                        "Token reponse was of type %s not dict",
                        type(token_response),
                    )
                # No get used here fail fast, means json structure has changed
                # and needs to be updated
                self.token = token_response["access_token"]
                self.token_expiry = time.time() + (
                    token_response["expires_in"] - random.randint(30, 120)
                )
                logger.debug("Spotify token has been set")

        except aiohttp.ClientResponseError as e:
            if e.status >= 500:
                logger.info("%s retrying...", e.status)
                return await self.get_token(max_attempts - 1)
            logger.error("%s: %s", e.status, e.message)
            # One second sleep time should be fine for now
            await asyncio.sleep(1)
            return None

    # TODO: spotify clean up next
    def spotify_multi_helper_func(self):
        pass

    def get_spotify_info(self, path_type: str, id: str) -> Playlist | Song | None:
        pass


def yt_json_parser(entries: list[dict[str, Any]]) -> list[Song] | None:
    songs: list[Song] = []
    for e in entries:
        songs.append(Song.from_json(e))

    return songs if songs else None


def search_query(query: str) -> Song | None:
    """
    YoutubeDL uses blocking calls use to_thread
    Returns a Song with the greatest result for the given query
    """
    # REMOVE THIS COMMENT AFTER REVIEW
    # Changed search function to use ytsearch
    try:
        with YoutubeDL(params=YDL_OPTS) as ydl:
            result = ydl.extract_info(
                f"ytsearch3:{query}", download=False, process=False
            )
            entries = result.get("entries")
            if not entries:
                # This differs from get_youtube_info as this function
                # only handles search queries and not direct links
                logger.warning("Entries returned none for %s", query)
                return None
            songs = [Song.from_json(e) for e in entries if e]
            # Filter out channel results
            songs = [s for s in songs if "channel/" not in s.webpage_url]
            return Playlist(songs).greatest_view_count()

    except DownloadError as e:
        logger.error("%s", e)
        return None


def get_youtube_info(url: str) -> Playlist | Song | None:
    # Currently removed the old regex that checked for &
    # in song link that was mostly to filter out &radio
    # which would load a giant playlist when the user might
    # have only expected one song(Retard protection)
    # Unsure if I want to keep this feature removed
    try:
        with YoutubeDL(params=YDL_OPTS) as ydl:
            result = ydl.extract_info(url, download=False, process=False)
            entries = result.get("entries")
            # I think if entries is blank its a direct link
            # and otherwise its a playlist
            # TODO: test this
            if not entries:
                # Ignore is okay here result is still a dict[str, Any]
                return Song.from_json(result)  # pyright: ignore
            else:
                # See above ignore comment
                playlist = Playlist.from_json(result, entries)  # pyright: ignore
                if not playlist.songs:
                    return None
                return playlist
    except DownloadError as e:
        logger.error("%s", e)
        return None


def _get_audio_source(query: Song):
    query


async def get_audio_source(query: Song):
    return await asyncio.to_thread(_get_audio_source, query)
