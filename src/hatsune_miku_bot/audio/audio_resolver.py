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
from urllib.parse import quote_plus, urlparse

import aiohttp
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, PagedList

from hatsune_miku_bot.audio.song_playlist_classes import Playlist, Song
from hatsune_miku_bot.logging.logging_setup import YTDLPLogger

if TYPE_CHECKING:
    from yt_dlp import _Params
else:
    _Params = dict[str, Any]

logger = logging.getLogger(__name__)

YT_DLP_LOGGER = YTDLPLogger()
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
YOUTUBE_INFO_PARAMS: _Params = {
    "allowed_extractors": ["youtube", "youtube:tab", "end"],
    "js_runtimes": {"node": {}},
    "quiet": True,
    "extractor_args": {"youtube": {"skip": ["hls", "dash", "translated_subs"]}},
    "logger": YT_DLP_LOGGER,
}
SEARCH_PARAMS: _Params = {
    "allowed_extractors": ["youtube:search", "end"],
    "quiet": True,
    "logger": YT_DLP_LOGGER,
}
SOUNDCLOUD_INFO_PARAMS: _Params = {
    "allowed_extractors": ["soundcloud", "end"],
    "quiet": True,
    "logger": YT_DLP_LOGGER,
}
SPOTIFY_SEARCH_PARAMS: _Params = {
    "allowed_extractors": ["youtube:music:search_url", "end"],
    "quiet": True,
    "logger": YT_DLP_LOGGER,
}
YOUTUBE_AUDIO_PARAMS: _Params = {
    "allowed_extractors": ["youtube", "end"],
    "format": "bestaudio/best",
    "js_runtimes": {"node": {}},
    "noplaylist": True,
    "quiet": True,
    "logger": YT_DLP_LOGGER,
}
SOUNDCLOUD_AUDIO_PARAMS: _Params = {
    "allowed_extractors": ["soundcloud", "end"],
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "logger": YT_DLP_LOGGER,
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
            logger.warning(
                "Spotify credentials were unavailable",
                extra={
                    "event": "spotify_credentials_missing",
                    "audio_provider": "spotify",
                },
            )
            return None
        if self.token and time.time() < self.token_expiry:
            logger.debug(
                "Token already cached, token expiry at %d",
                int(self.token_expiry),
                extra={
                    "event": "spotify_token_cache_hit",
                    "audio_provider": "spotify",
                    "token_expiry": int(self.token_expiry),
                },
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
                        "Spotify token response was %s instead of a dictionary",
                        type(token_response).__name__,
                        extra={
                            "event": "spotify_token_response_invalid",
                            "audio_provider": "spotify",
                            "response_type": type(token_response).__name__,
                        },
                    )
                # No 'get' used here so fail fast, means json structure has
                # changed and needs to be updated
                self.token = token_response["access_token"]
                self.token_expiry = time.time() + (
                    token_response["expires_in"] - random.randint(30, 120)
                )
                logger.debug(
                    "Spotify token was refreshed",
                    extra={
                        "event": "spotify_token_refreshed",
                        "audio_provider": "spotify",
                        "token_expiry": int(self.token_expiry),
                    },
                )

        except aiohttp.ClientResponseError as e:
            if e.status >= 500:
                logger.info(
                    "Spotify token request returned %s; retrying",
                    e.status,
                    extra={
                        "event": "spotify_token_request_retrying",
                        "audio_provider": "spotify",
                        "status_code": e.status,
                        "attempts_remaining": max_attempts - 1,
                        "exception": str(e),
                    },
                )
                # One second sleep time should be fine for now
                await asyncio.sleep(1)
                return await self.get_token(max_attempts - 1)
            logger.error(
                "Spotify token request failed with status %s: %s",
                e.status,
                e.message,
                extra={
                    "event": "spotify_token_request_failed",
                    "audio_provider": "spotify",
                    "status_code": e.status,
                    "exception": str(e),
                },
            )
            return None
        except (aiohttp.ClientError, TimeoutError) as e:
            if max_attempts > 1:
                logger.warning(
                    "Spotify token request failed; retrying with "
                    "%d attempts left: %s",
                    max_attempts - 1,
                    e,
                    extra={
                        "event": "spotify_token_request_retrying",
                        "audio_provider": "spotify",
                        "attempts_remaining": max_attempts - 1,
                        "exception": str(e),
                    },
                )
                await asyncio.sleep(1)
                return await self.get_token(max_attempts - 1)
            logger.error(
                "Spotify token request failed: %s",
                e,
                extra={
                    "event": "spotify_token_request_failed",
                    "audio_provider": "spotify",
                    "attempts_remaining": 0,
                    "exception": str(e),
                },
            )
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
                "Spotify request retry budget was exhausted",
                extra={
                    "event": "spotify_request_retry_budget_exhausted",
                    "audio_provider": "spotify",
                    "attempts_remaining": 0,
                    "request_url": link,
                },
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
            if max_attempts <= 1:
                logger.warning(
                    "Spotify request retry budget was exhausted",
                    extra={
                        "event": "spotify_request_retry_budget_exhausted",
                        "audio_provider": "spotify",
                        "status_code": e.status,
                        "attempts_remaining": 0,
                        "request_url": link,
                        "exception": str(e),
                    },
                )
                return None
            if e.status < 500 and e.status not in (401, 429):
                logger.warning(
                    "Spotify request returned unhandled status %d",
                    e.status,
                    extra={
                        "event": "spotify_request_status_unhandled",
                        "audio_provider": "spotify",
                        "status_code": e.status,
                        "request_url": link,
                        "exception": str(e),
                    },
                )
                return None
            if e.status >= 500:
                logger.debug(
                    "Spotify request returned %s; retrying",
                    e.status,
                    extra={
                        "event": "spotify_request_retrying",
                        "audio_provider": "spotify",
                        "status_code": e.status,
                        "attempts_remaining": max_attempts - 1,
                        "request_url": link,
                        "exception": str(e),
                    },
                )
                # One second sleep time should be fine for now
                await asyncio.sleep(1)
            if e.status == 401:
                logger.debug(
                    "Spotify rejected the cached token; requesting a new token",
                    extra={
                        "event": "spotify_token_rejected",
                        "audio_provider": "spotify",
                        "status_code": e.status,
                        "request_url": link,
                    },
                )
                self.token = None
                self.token_expiry = -1
                await self.get_token()
            if e.status == 429:
                if e.headers and (delay := e.headers.get("Retry-After")):
                    delay = float(delay) + random.randint(5, 10)
                    logger.debug(
                        "Spotify rate limit supplied a %.2f second retry delay",
                        delay,
                        extra={
                            "event": "spotify_rate_limit_delay_received",
                            "audio_provider": "spotify",
                            "status_code": e.status,
                            "attempts_remaining": max_attempts - 1,
                            "retry_delay_seconds": delay,
                            "request_url": link,
                        },
                    )
                else:
                    delay = 60
                    logger.debug(
                        "Spotify rate limit did not supply a retry delay; "
                        "using default",
                        extra={
                            "event": "spotify_rate_limit_delay_defaulted",
                            "audio_provider": "spotify",
                            "status_code": e.status,
                            "attempts_remaining": max_attempts - 1,
                            "retry_delay_seconds": delay,
                            "request_url": link,
                        },
                    )
                await asyncio.sleep(delay)
            return await self.spotify_get_request(
                link, params, max_attempts - 1
            )
        except (aiohttp.ClientError, TimeoutError) as e:
            if max_attempts > 1:
                logger.warning(
                    "Spotify request failed for %s; retrying with "
                    "%d attempts left: %s",
                    link,
                    max_attempts - 1,
                    e,
                    extra={
                        "event": "spotify_request_retrying",
                        "audio_provider": "spotify",
                        "attempts_remaining": max_attempts - 1,
                        "request_url": link,
                        "exception": str(e),
                    },
                )
                await asyncio.sleep(1)
                return await self.spotify_get_request(
                    link, params, max_attempts - 1
                )
            logger.error(
                "Spotify request failed for %s: %s",
                link,
                e,
                extra={
                    "event": "spotify_request_failed",
                    "audio_provider": "spotify",
                    "attempts_remaining": 0,
                    "request_url": link,
                    "exception": str(e),
                },
            )
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
                    "Spotify album metadata was unavailable for %s",
                    id,
                    extra={
                        "event": "spotify_metadata_missing",
                        "audio_provider": "spotify",
                        "resource_type": "album",
                        "resource_id": id,
                    },
                )
                return None
            song_information = await self.spotify_get_paginated_request(
                SP_ALBUM_LINK + id + "/tracks",
                params=SP_ALBUM_SONG_METADATA,
            )
            if not song_information:
                logger.warning(
                    "Spotify album tracks were unavailable for %s",
                    id,
                    extra={
                        "event": "spotify_tracks_missing",
                        "audio_provider": "spotify",
                        "resource_type": "album",
                        "resource_id": id,
                    },
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
                    "Spotify playlist metadata was unavailable for %s",
                    id,
                    extra={
                        "event": "spotify_metadata_missing",
                        "audio_provider": "spotify",
                        "resource_type": "playlist",
                        "resource_id": id,
                    },
                )
                return None
            song_information = await self.spotify_get_paginated_request(
                SP_PLAYLIST_LINK + id + "/tracks",
                params=SP_PLAYLIST_SONG_METADATA,
            )
            if not song_information:
                logger.warning(
                    "Spotify playlist tracks were unavailable for %s",
                    id,
                    extra={
                        "event": "spotify_tracks_missing",
                        "audio_provider": "spotify",
                        "resource_type": "playlist",
                        "resource_id": id,
                    },
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
                logger.warning(
                    "Spotify track metadata was unavailable for %s",
                    id,
                    extra={
                        "event": "spotify_metadata_missing",
                        "audio_provider": "spotify",
                        "resource_type": "track",
                        "resource_id": id,
                    },
                )
                return None
            return Song.from_spotify(song, "")
        logger.warning(
            "Spotify resource type could not be determined from %s",
            path_type,
            extra={
                "event": "spotify_resource_type_unrecognized",
                "audio_provider": "spotify",
                "path_type": path_type,
            },
        )
        return None

    def get_soundcloud_info(self, url: str) -> Song | None:
        if re.match(r"(.*sets+.*)(?:\?)", url):
            logger.info(
                "SoundCloud playlists are not supported",
                extra={
                    "event": "soundcloud_playlist_unsupported",
                    "audio_provider": "soundcloud",
                    "source_url": url,
                },
            )
            return None
        try:
            with YoutubeDL(params=SOUNDCLOUD_INFO_PARAMS) as ydl:
                result = ydl.extract_info(url, download=False)
                restricted = True
                formats = result.get("formats")
                if formats:
                    for key in formats:
                        if "http_mp3" in key["format_id"]:
                            restricted = False
                    if restricted:
                        logger.info(
                            "SoundCloud HTTP MP3 format was unavailable",
                            extra={
                                "event": "soundcloud_audio_format_unavailable",
                                "audio_provider": "soundcloud",
                                "source_url": url,
                            },
                        )
                        return None
                    return Song.from_yt_dlp(result)
                logger.error(
                    "SoundCloud response did not include audio formats for %s",
                    url,
                    extra={
                        "event": "soundcloud_formats_missing",
                        "audio_provider": "soundcloud",
                        "source_url": url,
                    },
                )
                return None
        except DownloadError as e:
            logger.error(
                "SoundCloud metadata download failed: %s",
                e,
                extra={
                    "event": "soundcloud_metadata_download_failed",
                    "audio_provider": "soundcloud",
                    "source_url": url,
                    "exception": str(e),
                },
            )
            return None

    def search_query(self, query: str) -> Song | None:
        """
        YoutubeDL uses blocking calls use to_thread
        Returns a Song with the greatest view count
        """
        try:
            with YoutubeDL(params=SEARCH_PARAMS) as ydl:
                result = ydl.extract_info(
                    f"ytsearch3:{query}", download=False, process=False
                )
                entries = result.get("entries")
                if not entries:
                    # This differs from get_youtube_info as this function
                    # only handles search queries and not direct links
                    logger.warning(
                        "YouTube search returned no entries for %s",
                        query,
                        extra={
                            "event": "youtube_search_entries_missing",
                            "audio_provider": "youtube",
                            "query": query,
                        },
                    )
                    return None
                songs = [Song.from_yt_dlp(e) for e in entries if e]
                # Filter out channel results
                songs = [s for s in songs if "channel/" not in s.webpage_url]
                if not songs:
                    return None
                return Playlist(songs).greatest_view_count()

        except DownloadError as e:
            logger.error(
                "YouTube search failed: %s",
                e,
                extra={
                    "event": "youtube_search_failed",
                    "audio_provider": "youtube",
                    "query": query,
                    "exception": str(e),
                },
            )
            return None

    def get_youtube_info(self, url: str) -> Playlist | Song | None:
        # Currently removed the old regex that checked for &
        # in song link that was mostly to filter out &radio
        # which would load a giant playlist when the user might
        # have only expected one song(Retard protection)
        # Unsure if I want to keep this feature removed
        try:
            with YoutubeDL(params=YOUTUBE_INFO_PARAMS) as ydl:
                result = ydl.extract_info(url, download=False, process=False)
                if "entries" not in result:
                    return Song.from_yt_dlp_direct_link(result)
                entries = result.get("entries")
                if isinstance(entries, PagedList):
                    logger.debug(
                        "YouTube returned a paged playlist for %s",
                        url,
                        extra={
                            "event": "youtube_paged_playlist_unsupported",
                            "audio_provider": "youtube",
                            "source_url": url,
                        },
                    )
                    return None
                if entries is None:
                    logger.debug(
                        "YouTube returned no playlist entries for %s",
                        url,
                        extra={
                            "event": "youtube_playlist_entries_missing",
                            "audio_provider": "youtube",
                            "source_url": url,
                        },
                    )
                    return None
                playlist = Playlist.from_yt_dlp(result, entries)
                if not playlist.songs:
                    return None
                return playlist
        except DownloadError as e:
            logger.error(
                "YouTube metadata download failed: %s",
                e,
                extra={
                    "event": "youtube_metadata_download_failed",
                    "audio_provider": "youtube",
                    "source_url": url,
                    "exception": str(e),
                },
            )
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
        if url_domain == "on.soundcloud.com/":
            logger.info(
                "SoundCloud short links are not supported",
                extra={
                    "event": "soundcloud_short_link_unsupported",
                    "audio_provider": "soundcloud",
                    "source_url": url,
                },
            )
            return None
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
    with YoutubeDL(SPOTIFY_SEARCH_PARAMS) as ydl:
        pattern = re.compile(r"(?<!\S)(-|#|@)(?=\S)")
        p2 = re.compile(r"(?<=\S)\|(?=\S)")
        safe_title = pattern.sub("- ", quote_plus(query.title))
        safe_title = p2.sub(" | ", safe_title)
        result = ydl.extract_info(
            f"https://music.youtube.com/search?q={safe_title}#songs",
            download=False,
            process=False,
        )
        entries = result.get("entries")
        if not entries or isinstance(entries, PagedList):
            logger.debug(
                "YouTube Music search returned no usable entries",
                extra={
                    "event": "spotify_source_search_entries_unavailable",
                    "audio_provider": "youtube_music",
                    "song_title": query.title,
                    "source_url": query.webpage_url,
                },
            )
            return None
        songs = [
            Song.from_yt_dlp(entry)
            # Testing 2 for now instead of 3 to see if it improves results
            for entry in islice(filter(None, entries), 2)
        ]
        if not songs:
            logger.warning(
                "YouTube Music search returned no songs for %s[%s]",
                query.title,
                query.webpage_url,
                extra={
                    "event": "spotify_source_search_results_missing",
                    "audio_provider": "youtube_music",
                    "song_title": query.title,
                    "source_url": query.webpage_url,
                },
            )
            return None
        end_song = rank_spotify_search_results(songs, query)
        if not end_song.webpage_url:
            logger.info(
                "Unable to find valid URL for %s, link: %s",
                query.title,
                query.webpage_url,
                extra={
                    "event": "spotify_source_url_missing",
                    "audio_provider": "youtube_music",
                    "song_title": query.title,
                    "source_url": query.webpage_url,
                },
            )
            return None
        with YoutubeDL(YOUTUBE_AUDIO_PARAMS) as ydl:
            resolved = ydl.extract_info(
                url=end_song.webpage_url, download=False
            )
            logger.info(
                "Loaded audio for spotify link: %s, %s, Resolved to: [%s]%s",
                query.title,
                query.webpage_url,
                end_song.title,
                end_song.webpage_url,
                extra={
                    "event": "spotify_audio_source_resolved",
                    "audio_provider": "youtube_music",
                    "song_title": query.title,
                    "source_url": query.webpage_url,
                    "resolved_title": end_song.title,
                },
            )
            return resolved.get("url")


def _get_audio_source_impl(query: Song) -> str | None:
    try:
        if "spotify" in query.webpage_url:
            return _get_spotify_source_impl(query)
        hostname = urlparse(query.webpage_url).hostname
        if not hostname:
            logger.debug(
                "Audio source URL did not contain a hostname for %s",
                query,
                extra={
                    "event": "audio_source_hostname_missing",
                    "song_title": query.title,
                    "source_url": query.webpage_url,
                },
            )
            return None
        if "soundcloud" in hostname:
            params = SOUNDCLOUD_AUDIO_PARAMS
            audio_provider = "soundcloud"
        else:
            params = YOUTUBE_AUDIO_PARAMS
            audio_provider = "youtube"
        with YoutubeDL(params) as ydl:
            result = ydl.extract_info(url=query.webpage_url, download=False)
            logger.info(
                "Loaded audio for non-spotify link: %s, %s",
                query.title,
                query.webpage_url.replace("https://", ""),
                extra={
                    "event": "audio_source_resolved",
                    "audio_provider": audio_provider,
                    "song_title": query.title,
                    "source_url": query.webpage_url,
                },
            )
            return result.get("url")
    except DownloadError as e:
        logger.error(
            "Audio source download failed: %s",
            e,
            extra={
                "event": "audio_source_download_failed",
                "song_title": query.title,
                "source_url": query.webpage_url,
                "exception": str(e),
            },
        )
        return None
    except Exception:
        logger.exception(
            "Audio source resolution failed unexpectedly",
            extra={
                "event": "audio_source_resolution_unexpected_failure",
                "song_title": query.title,
                "source_url": query.webpage_url,
            },
        )
        return None


async def get_audio_source(query: Song) -> str | None:
    return await asyncio.to_thread(_get_audio_source_impl, query)
