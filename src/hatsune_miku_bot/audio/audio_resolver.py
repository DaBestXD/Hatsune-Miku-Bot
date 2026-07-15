import asyncio
import base64
import logging
import os
import random
import re
import time
from typing import Any

import aiohttp
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, PagedList

from hatsune_miku_bot.audio.song_playlist_classes import Playlist, Song
from hatsune_miku_bot.bot_config.constants import (
    AUDIO_OPTS,
    SP_ALBUM_LINK,
    SP_ALBUM_METADATA,
    SP_ALBUM_SONG_METADATA,
    SP_PLAYLIST_LINK,
    SP_PLAYLIST_METADATA,
    SP_PLAYLIST_SONG_METADATA,
    SP_TRACK_LINK,
    SPOTIFY_SEARCH_OPTS,
    YDL_OPTS,
)

logger = logging.getLogger(__name__)


class AudioInfoResolver:
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
                "Token already cached, token expiry at %d",
                int(self.token_expiry),
            )
            return None
        if max_attempts <= 0:
            return None
        auth_string = f"{self.client_id}:{self.client_secret}".encode("utf-8")
        url = "https://accounts.spotify.com/api/token"
        auth_base64 = str(base64.b64encode(auth_string), "utf-8")
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
                # No 'get' used here so fail fast, means json structure has changed  # noqa: E501
                # and needs to be updated
                self.token = token_response["access_token"]
                self.token_expiry = time.time() + (
                    token_response["expires_in"] - random.randint(30, 120)
                )
                logger.debug("Spotify token has been set")

        except aiohttp.ClientResponseError as e:
            if e.status >= 500:
                logger.info("%s retrying...", e.status)
                # One second sleep time should be fine for now
                await asyncio.sleep(1)
                return await self.get_token(max_attempts - 1)
            logger.error("%s: %s", e.status, e.message)
            return None
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if max_attempts > 1:
                logger.warning(
                    "Spotify token request failed, retrying... (%d attempts left): %s",  # noqa: E501
                    max_attempts - 1,
                    e,
                )
                await asyncio.sleep(1)
                return await self.get_token(max_attempts - 1)
            logger.error("Spotify token request failed: %s", e)
            return None

    async def spotify_get_request(
        self, link: str, params: dict[str, str], max_attempts: int = 3
    ) -> dict[str, Any] | None:
        if not self.token:
            await self.get_token()
        if not self.token:
            return None
        if max_attempts <= 0:
            logger.warning(
                "Max attempts reached for %s", self.spotify_get_request.__name__
            )
            return None
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            async with self.client.get(
                link, headers=headers, params=params
            ) as res:
                res.raise_for_status()
                return await res.json()
        except aiohttp.ClientResponseError as e:
            logger.error("Spotify get request error: %d", e.status)
            if e.status >= 500:
                logger.info("%s retrying...", e.status)
                # One second sleep time should be fine for now
                await asyncio.sleep(1)
                return await self.spotify_get_request(
                    link, params, max_attempts - 1
                )
            logger.error("%s: %s", e.status, e.message)
            return None
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if max_attempts > 1:
                logger.warning(
                    "Spotify get request failed for %s, retrying... (%d attempts left): %s",  # noqa: E501
                    link,
                    max_attempts - 1,
                    e,
                )
                await asyncio.sleep(1)
                return await self.spotify_get_request(
                    link, params, max_attempts - 1
                )
            logger.error("Spotify get request failed for %s: %s", link, e)
            return None

    async def get_spotify_info(
        self, path_type: str, id: str
    ) -> Playlist | Song | None:
        if "album/" in path_type:
            container_metadata = await self.spotify_get_request(
                SP_ALBUM_LINK + id,
                params=SP_ALBUM_METADATA,
            )
            if not container_metadata:
                logger.warning(
                    "Failed to get metadata response back for %s[Album]", id
                )
                return None
            song_information = await self.spotify_get_request(
                SP_ALBUM_LINK + id + "/tracks",
                params=SP_ALBUM_SONG_METADATA,
            )
            if not song_information:
                logger.warning(
                    "Failed to get song information back for %s[Album]", id
                )
                return None
            return Playlist.from_spotify(
                path_type,
                container_metadata,
                song_information,
                is_album=True,
            )

        if "playlist/" in path_type:
            container_metadata = await self.spotify_get_request(
                SP_PLAYLIST_LINK + id,
                params=SP_PLAYLIST_METADATA,
            )
            if not container_metadata:
                logger.warning(
                    "Failed to get metadata response back for %s[Playlist]", id
                )
                return None
            song_information = await self.spotify_get_request(
                SP_PLAYLIST_LINK + id + "/tracks",
                params=SP_PLAYLIST_SONG_METADATA,
            )
            if not song_information:
                logger.warning(
                    "Failed to get song information back for %s[Playlist]", id
                )
                return None
            return Playlist.from_spotify(
                path_type,
                container_metadata,
                song_information,
                is_album=False,
            )
        if "track/" in path_type:
            song = await self.spotify_get_request(
                SP_TRACK_LINK + id,
                params={"market": "US"},
            )
            if not song:
                logger.warning("Failed to get response back for %s[Track]", id)
                return None
            return Song.from_spotify(song, "")
        logger.warning("Regex failed for %s", path_type)
        return None

    def get_soundcloud_info(self, url: str) -> Song | None:
        # TODO: fix this later
        # if re.match(r"(.*sets+.*)(?:\?)", url):
        #     logger.info("Soundcloud playlist was entered")
        #     return None
        # try:
        #     with YoutubeDL(params=YDL_OPTS) as ydl:
        #         result = ydl.extract_info(url, download=False)
        #         restricted = True
        #         formats = result.get("formats")
        #         result = cast(dict[str, str | None], result)
        #         if formats:
        #             for key in formats:
        #                 if "http_mp3" in key["format_id"]:
        #                     restricted = False
        #             if restricted:
        #                 logger.info("Unable to retrieve soundcloud http_mp3")
        #                 return None
        #             song = yt_json_parser([result], EXTRACT_VALS)
        #             if song:
        #                 return song[0]
        #             else:
        #                 logger.error("Song information empty: %s", url)
        #                 return None
        #         logger.error(
        #             "Regex failed for soundcloud info, Formats: %s Title: %s", formats, url  # noqa: E501
        #         )
        #         return None
        # except DownloadError as e:
        #     logger.error("Soundcloud download error: %s", e)
        #     return None
        raise NotImplementedError("Sound cloud fix later")

    def search_query(self, query: str) -> Song | None:
        """
        YoutubeDL uses blocking calls use to_thread
        Returns a Song with the greatest view count
        """
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
                songs = [Song.from_yt_dlp(e) for e in entries if e]
                # Filter out channel results
                songs = [s for s in songs if "channel/" not in s.webpage_url]
                return Playlist(songs).greatest_view_count()

        except DownloadError as e:
            logger.error("%s", e)
            return None

    def get_youtube_info(self, url: str) -> Playlist | Song | None:
        # Currently removed the old regex that checked for &
        # in song link that was mostly to filter out &radio
        # which would load a giant playlist when the user might
        # have only expected one song(Retard protection)
        # Unsure if I want to keep this feature removed
        try:
            with YoutubeDL(params=YDL_OPTS) as ydl:
                result = ydl.extract_info(url, download=False, process=False)
                entries = result.get("entries")
                if isinstance(entries, PagedList):
                    logger.debug("YDL returned page list")
                    return None
                if not entries:
                    return Song.from_yt_dlp(result)
                else:
                    playlist = Playlist.from_yt_dlp(result, entries)
                    if not playlist.songs:
                        return None
                    return playlist
        except DownloadError as e:
            logger.error("%s", e)
            return None

    async def get_song_info(self, url: str) -> Playlist | Song | None:
        """
        Use regex to seperate each user request
        """
        grouped_url = re.match(r"(?:https://)([a-z.]+/)(.*)", url)
        if grouped_url is None:
            return await asyncio.to_thread(self.search_query, url)
        url_domain = grouped_url.group(1)
        url_path = grouped_url.group(2)
        if "spotify" in url_domain:
            re_groups = re.match(
                r"(track/|playlist/|album/)(\w+)(?:\?|$)", url_path
            )
            if re_groups:
                id = re_groups.group(2)
                return await self.get_spotify_info(url, id)
        if "youtube" in url_domain or "youtu.be" in url_domain:
            return await asyncio.to_thread(self.get_youtube_info, url)
        if "soundcloud" in url_domain:
            return await asyncio.to_thread(self.get_soundcloud_info, url)
        return None


def _get_spotify_source_impl(query: Song) -> str | None:
    with YoutubeDL(SPOTIFY_SEARCH_OPTS) as ydl:
        result = ydl.extract_info(
            f"ytsearch3:{query.title}", download=False, process=False
        )
        entries = result.get("entries")
        # tuple of viewcount and source url
        songs: list[tuple[int, str | None]] = []
        if not entries:
            logger.info(
                "Unable to find entries for %s, link: %s",
                query.title,
                query.webpage_url,
            )
            return None

        for n in entries:
            if not isinstance(n, dict):
                continue
            url = n.get("url") or None
            view_count: int = n.get("view_count") or 0
            songs.append((view_count, url))

        if not songs:
            logger.info(
                "Unable to find valid entries for %s, link: %s",
                query.title,
                query.webpage_url,
            )
            return None

        _, url = max(songs)
        if not url:
            logger.info(
                "Unable to find valid URL for %s, link: %s",
                query.title,
                query.webpage_url,
            )
            return None
        with YoutubeDL(AUDIO_OPTS) as ydl:
            resolved = ydl.extract_info(url=url, download=False)
            logger.info(
                "Loaded audio for spotify link: %s, %s, Resolved to: %s",
                query.title,
                query.webpage_url,
                url,
            )
            return resolved.get("url")


def _get_audio_source_impl(query: Song) -> str | None:
    try:
        if "spotify" in query.webpage_url:
            # TODO: implement fuzzy seach later refer to older commit logic
            return _get_spotify_source_impl(query)
        else:
            with YoutubeDL(AUDIO_OPTS) as ydl:
                result = ydl.extract_info(url=query.webpage_url, download=False)
                logger.info(
                    "Loaded audio for non-spotify link: %s, %s",
                    query.title,
                    query.webpage_url.replace("https://", ""),
                )
                return result.get("url")
    except DownloadError as e:
        logger.error("Audio source download error: %s", e)
        return None
    except Exception as e:
        logger.critical("Audio failed in unexpected way: %s", e)
        return None


async def get_audio_source(query: Song):
    return await asyncio.to_thread(_get_audio_source_impl, query)
