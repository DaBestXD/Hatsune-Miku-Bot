import asyncio
import base64
import logging
import os
import random
import re
import time
from difflib import SequenceMatcher
from itertools import islice
from typing import TYPE_CHECKING, Any
from urllib.parse import quote_plus

import aiohttp
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, PagedList

from hatsune_miku_bot.audio.song_playlist_classes import Playlist, Song

if TYPE_CHECKING:
    from yt_dlp import _Params
else:
    _Params = dict[str, Any]

logger = logging.getLogger(__name__)


SP_PLAYLIST_SONG_METADATA = {
    "market": "US",
    "fields": "items(track(name,duration_ms,artists(name),external_urls(spotify),album(images(url)))),next,total",  # noqa: E501
}
SP_PLAYLIST_METADATA = {
    "market": "US",
    "fields": "name,images(url),tracks(total)",
}
SP_ALBUM_SONG_METADATA = {
    "market": "US",
    "fields": "items(name,duration_ms,artists(name),external_urls(spotify)),next,total",  # noqa: E501
}
SP_ALBUM_METADATA = {
    "market": "US",
    "fields": "name,total_tracks,images(url)",
}
SP_ALBUM_LINK = "https://api.spotify.com/v1/albums/"
SP_TRACK_LINK = "https://api.spotify.com/v1/tracks/"
SP_PLAYLIST_LINK = "https://api.spotify.com/v1/playlists/"
YDL_OPTS: _Params = {
    "default_search": "ytsearch2",
    "js_runtimes": {"node": {}},
    "extract_flat": "in_playlist",
    "remote_components": {"ejs:github"},
    "quiet": True,
    "extractor_args": {"youtube": {"skip": ["hls", "dash", "translated_subs"]}},
}
AUDIO_OPTS: _Params = {
    "format": "bestaudio/best",
    "js_runtimes": {"node": {}},
    "default_search": "ytsearch2",
    "remote_components": {"ejs:github"},
    "noplaylist": True,
    "playlist_items": "1-2",
    "quiet": True,
}
SPOTIFY_SEARCH_OPTS: _Params = {
    "default_search": f"ytsearch{3}",
    "js_runtimes": {"node": {}},
    "extract_flat": "in_playlist",
    "remote_components": {"ejs:github"},
    "noplaylist": True,
    "quiet": True,
}


class AudioInfoResolver:
    def __init__(self, client: aiohttp.ClientSession):
        self.client_id = os.getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        self.token: str | None = None
        self.token_expiry: float = -1
        self.client = client

    async def spotify_get_paginated_request(
        self,
        link: str,
        params: dict[str, str],
    ) -> dict[str, Any] | None:
        items: list[dict[str, Any]] = []
        next_link: str | None = link
        next_params = params

        # no get used/or typing checks, fail fast to alert for json changes
        while next_link:
            page = await self.spotify_get_request(next_link, next_params)
            if not page:
                return None
            page_items = page["items"]
            items.extend(item for item in page_items if isinstance(item, dict))
            next_value = page["next"]
            next_link = next_value
            next_params = {}
        if not items:
            return None
        return {"items": items}

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
        auth_string = f"{self.client_id}:{self.client_secret}".encode()
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
                # No 'get' used here so fail fast, means json structure has
                # changed and needs to be updated
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
        except (aiohttp.ClientError, TimeoutError) as e:
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
        if not self.token or self.token_expiry <= time.time():
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
        except (aiohttp.ClientError, TimeoutError) as e:
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
        """
        For spotify platlist/albums two api calls are required
        One for the actualy container metadata(playlist title, etc.)
        Another one for information about songs in the container
        """
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
            song_information = await self.spotify_get_paginated_request(
                SP_ALBUM_LINK + id + "/tracks",
                params=SP_ALBUM_SONG_METADATA,
            )
            if not song_information:
                logger.warning(
                    "Failed to get song information back for %s[Album]", id
                )
                return None
            playlist = Playlist.from_spotify(
                path_type,
                container_metadata,
                song_information,
                is_album=True,
            )
            if not playlist.songs:
                return None
            return playlist

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
            song_information = await self.spotify_get_paginated_request(
                SP_PLAYLIST_LINK + id + "/tracks",
                params=SP_PLAYLIST_SONG_METADATA,
            )
            if not song_information:
                logger.warning(
                    "Failed to get song information back for %s[Playlist]", id
                )
                return None
            playlist = Playlist.from_spotify(
                path_type,
                container_metadata,
                song_information,
                is_album=False,
            )
            if not playlist.songs:
                return None
            return playlist

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
        if re.match(r"(.*sets+.*)(?:\?)", url):
            logger.info("Soundcloud playlist was entered")
            return None
        try:
            with YoutubeDL(params=YDL_OPTS) as ydl:
                result = ydl.extract_info(url, download=False)
                restricted = True
                formats = result.get("formats")
                if formats:
                    for key in formats:
                        if "http_mp3" in key["format_id"]:
                            restricted = False
                    if restricted:
                        logger.info("Unable to retrieve soundcloud http_mp3")
                        return None
                    return Song.from_yt_dlp(result)
                logger.error(
                    "Regex failed for soundcloud info, Formats: %s Title: %s",
                    formats,
                    url,
                )
                return None
        except DownloadError as e:
            logger.error("Soundcloud download error: %s", e)
            return None

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
                if not songs:
                    return None
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
                if "entries" not in result:
                    return Song.from_yt_dlp_direct_link(result)
                entries = result.get("entries")
                if isinstance(entries, PagedList):
                    logger.debug("YDL returned page list for %s", url)
                    return None
                if entries is None:
                    logger.debug("Entries returned none for %s", url)
                    return None
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


def rank_spotify_search_results(songs: list[Song], query: Song) -> Song:
    str_song__to_match = query.normalize_song_title()
    matches: list[tuple[Song, float]] = []
    for s in songs:
        ratio = SequenceMatcher(
            None,
            str_song__to_match,
            s.normalize_song_title(),
        ).ratio()
        matches.append((s, ratio))
    return max(matches, key=lambda song: song[1])[0]


def _get_spotify_source_impl(query: Song) -> str | None:
    with YoutubeDL(SPOTIFY_SEARCH_OPTS) as ydl:
        result = ydl.extract_info(
            f"https://music.youtube.com/search?q={quote_plus(query.title)}#songs",
            download=False,
            process=False,
        )
        entries = result.get("entries")
        if not entries or isinstance(entries, PagedList):
            logger.debug("Entries returned none or PagedList")
            return None
        songs = [
            Song.from_yt_dlp(entry)
            for entry in islice(filter(None, entries), 3)
        ]
        if not songs:
            logger.warning(
                "No songs returned for %s[%s]",
                query.title,
                query.webpage_url,
            )
            return None
        end_song = rank_spotify_search_results(songs, query)
        if not end_song.webpage_url:
            logger.info(
                "Unable to find valid URL for %s, link: %s",
                query.title,
                query.webpage_url,
            )
            return None
        with YoutubeDL(AUDIO_OPTS) as ydl:
            resolved = ydl.extract_info(
                url=end_song.webpage_url, download=False
            )
            logger.info(
                "Loaded audio for spotify link: %s, %s, Resolved to: [%s]%s",
                query.title,
                query.webpage_url,
                end_song.title,
                end_song.webpage_url,
            )
            return resolved.get("url")


def _get_audio_source_impl(query: Song) -> str | None:
    try:
        if "spotify" in query.webpage_url:
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
