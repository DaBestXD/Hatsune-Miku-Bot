from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import aiohttp
from yt_dlp.utils import DownloadError

import hatsune_miku_bot.audio.audio_resolver as resolver
from hatsune_miku_bot.audio.song_playlist_classes import Playlist, Song


def as_any(value: object) -> Any:
    return value


class AsyncResponseContext:
    def __init__(
        self, response: object | None = None, error: Exception | None = None
    ):
        self.response = response
        self.error = error

    async def __aenter__(self):
        if self.error:
            raise self.error
        return self.response

    async def __aexit__(self, *_args: object) -> None:
        return None


def ydl_context(ydl: MagicMock) -> MagicMock:
    context = MagicMock()
    context.__enter__.return_value = ydl
    context.__exit__.return_value = None
    return context


def spotify_song() -> Song:
    return Song(
        "World is Mine - Hatsune Miku",
        "https://open.spotify.test/track/1",
        "https://image.test/cover.jpg",
        "210",
        "0",
    )


class SpotifyRequestTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_token_skips_missing_credentials_and_cached_token(
        self,
    ) -> None:
        client = SimpleNamespace(post=Mock())
        audio_resolver = resolver.AudioInfoResolver(as_any(client))
        audio_resolver.client_id = None
        audio_resolver.client_secret = None

        await audio_resolver.get_token()
        client.post.assert_not_called()

        audio_resolver.client_id = "client"
        audio_resolver.client_secret = "secret"
        audio_resolver.token = "cached"
        audio_resolver.token_expiry = 10_000
        with patch.object(resolver.time, "time", return_value=100):
            await audio_resolver.get_token()
        client.post.assert_not_called()

    async def test_get_token_retries_client_error_then_caches_token(
        self,
    ) -> None:
        response = SimpleNamespace(
            raise_for_status=Mock(),
            json=AsyncMock(
                return_value={"access_token": "new-token", "expires_in": 3600}
            ),
        )
        client = SimpleNamespace(
            post=Mock(
                side_effect=[
                    AsyncResponseContext(error=aiohttp.ClientConnectionError()),
                    AsyncResponseContext(response),
                ]
            )
        )
        audio_resolver = resolver.AudioInfoResolver(as_any(client))
        audio_resolver.client_id = "client"
        audio_resolver.client_secret = "secret"

        with (
            patch.object(resolver.asyncio, "sleep", new=AsyncMock()) as sleep,
            patch.object(resolver.random, "randint", return_value=60),
            patch.object(resolver.time, "time", return_value=100),
        ):
            await audio_resolver.get_token()

        self.assertEqual(audio_resolver.token, "new-token")
        self.assertEqual(audio_resolver.token_expiry, 3640)
        self.assertEqual(client.post.call_count, 2)
        sleep.assert_awaited_once_with(1)

    async def test_spotify_get_request_fetches_json_with_bearer_token(
        self,
    ) -> None:
        response = SimpleNamespace(
            raise_for_status=Mock(),
            json=AsyncMock(return_value={"name": "Miku"}),
        )
        client = SimpleNamespace(
            get=Mock(return_value=AsyncResponseContext(response))
        )
        audio_resolver = resolver.AudioInfoResolver(as_any(client))
        audio_resolver.token = "token"
        audio_resolver.token_expiry = float("inf")

        result = await audio_resolver.spotify_get_request(
            "https://api.spotify.test/track/1", {"market": "US"}
        )

        self.assertEqual(result, {"name": "Miku"})
        client.get.assert_called_once_with(
            "https://api.spotify.test/track/1",
            headers={"Authorization": "Bearer token"},
            params={"market": "US"},
        )

    async def test_get_spotify_info_routes_track_album_and_playlist(
        self,
    ) -> None:
        audio_resolver = resolver.AudioInfoResolver(as_any(SimpleNamespace()))
        track_payload = {
            "name": "Melt",
            "duration_ms": 200_000,
            "artists": [{"name": "ryo"}],
            "external_urls": {"spotify": "https://open.spotify.test/track/1"},
            "album": {"images": [{"url": "https://image.test/song.jpg"}]},
        }
        metadata = {
            "name": "Collection",
            "images": [{"url": "https://image.test/list.jpg"}],
        }

        with patch.object(
            audio_resolver,
            "spotify_get_request",
            new=AsyncMock(return_value=track_payload),
        ):
            track = await audio_resolver.get_spotify_info("track/1", "1")

        for path_type, is_album, item in (
            ("album/1", True, track_payload),
            ("playlist/1", False, {"track": track_payload}),
        ):
            with self.subTest(path_type=path_type):
                with patch.object(
                    audio_resolver,
                    "spotify_get_request",
                    new=AsyncMock(
                        side_effect=[
                            metadata,
                            {"items": [item], "next": None},
                        ]
                    ),
                ):
                    result = await audio_resolver.get_spotify_info(
                        path_type, "1"
                    )
                self.assertIsInstance(result, Playlist)
                self.assertEqual(as_any(result).length, 1)
                self.assertEqual(is_album, path_type.startswith("album"))

        self.assertIsInstance(track, Song)

    async def test_spotify_paginated_request_combines_all_pages(self) -> None:
        audio_resolver = resolver.AudioInfoResolver(as_any(SimpleNamespace()))
        first_item = {"name": "First"}
        second_item = {"name": "Second"}
        next_url = "https://api.spotify.test/tracks?offset=1"
        params = {"market": "US"}

        with patch.object(
            audio_resolver,
            "spotify_get_request",
            new=AsyncMock(
                side_effect=[
                    {"items": [first_item], "next": next_url},
                    {"items": [second_item], "next": None},
                ]
            ),
        ) as get_request:
            result = await audio_resolver.spotify_get_paginated_request(
                "https://api.spotify.test/tracks", params
            )

        self.assertEqual(result, {"items": [first_item, second_item]})
        self.assertEqual(
            get_request.await_args_list,
            [
                call("https://api.spotify.test/tracks", params),
                call(next_url, {}),
            ],
        )


class ResolverRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_song_info_routes_search_and_supported_domains(
        self,
    ) -> None:
        audio_resolver = resolver.AudioInfoResolver(as_any(SimpleNamespace()))
        expected = spotify_song()

        with patch.object(
            resolver.asyncio, "to_thread", new=AsyncMock(return_value=expected)
        ) as to_thread:
            self.assertIs(
                await audio_resolver.get_song_info("miku song"), expected
            )
            to_thread.assert_awaited_once_with(
                audio_resolver.search_query, "miku song"
            )

        with patch.object(
            audio_resolver,
            "get_spotify_info",
            new=AsyncMock(return_value=expected),
        ) as spotify_info:
            result = await audio_resolver.get_song_info(
                "https://open.spotify.com/track/abc123?si=1"
            )
            self.assertIs(result, expected)
            spotify_info.assert_awaited_once_with(
                "https://open.spotify.com/track/abc123?si=1", "abc123"
            )

        for url, method_name in (
            ("https://youtube.com/watch?v=1", "get_youtube_info"),
            ("https://youtu.be/1", "get_youtube_info"),
            ("https://soundcloud.com/miku/song", "get_soundcloud_info"),
        ):
            with self.subTest(url=url):
                method = getattr(audio_resolver, method_name)
                with patch.object(
                    resolver.asyncio,
                    "to_thread",
                    new=AsyncMock(return_value=expected),
                ) as to_thread:
                    self.assertIs(
                        await audio_resolver.get_song_info(url), expected
                    )
                    to_thread.assert_awaited_once_with(method, url)

        self.assertIsNone(
            await audio_resolver.get_song_info("https://example.test/song")
        )


class YtDlpResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.audio_resolver = resolver.AudioInfoResolver(
            as_any(SimpleNamespace())
        )

    def test_search_query_selects_playable_song_with_most_views(self) -> None:
        ydl = MagicMock()
        ydl.extract_info.return_value = {
            "entries": [
                {
                    "title": "Channel",
                    "url": "https://youtube.test/channel/miku",
                    "view_count": 10_000,
                },
                {
                    "title": "Lower",
                    "url": "https://youtube.test/watch?v=1",
                    "view_count": 10,
                },
                {
                    "title": "Higher",
                    "url": "https://youtube.test/watch?v=2",
                    "view_count": 20,
                },
            ]
        }

        with patch.object(
            resolver, "YoutubeDL", return_value=ydl_context(ydl)
        ) as ydl_class:
            result = self.audio_resolver.search_query("world is mine")

        self.assertIsNotNone(result)
        self.assertEqual(as_any(result).title, "Higher")
        ydl_class.assert_called_once_with(params=resolver.YDL_OPTS)
        ydl.extract_info.assert_called_once_with(
            "ytsearch3:world is mine", download=False, process=False
        )

    def test_search_query_returns_none_when_all_candidates_filtered(
        self,
    ) -> None:
        ydl = MagicMock()
        ydl.extract_info.return_value = {
            "entries": [
                {
                    "title": "Channel",
                    "url": "https://youtube.test/channel/miku",
                    "view_count": 10_000,
                },
                {
                    "title": "Topic Channel",
                    "url": "https://youtube.test/channel/topic",
                    "view_count": 20_000,
                },
            ]
        }

        with patch.object(resolver, "YoutubeDL", return_value=ydl_context(ydl)):
            result = self.audio_resolver.search_query("world is mine")

        self.assertIsNone(result)

    def test_get_youtube_info_returns_song_or_playlist(self) -> None:
        track_result = {
            "title": "Track",
            "url": None,
            "original_url": "https://youtube.test/watch?v=1",
            "duration": 60,
            "view_count": 5,
        }
        playlist_result = {
            "title": "Playlist",
            "original_url": "https://youtube.test/playlist?list=1",
            "entries": [track_result],
        }
        ydl = MagicMock()
        ydl.extract_info.side_effect = [track_result, playlist_result]

        with patch.object(resolver, "YoutubeDL", return_value=ydl_context(ydl)):
            track = self.audio_resolver.get_youtube_info(
                "https://youtube.test/1"
            )
            playlist = self.audio_resolver.get_youtube_info(
                "https://youtube.test/playlist?list=1"
            )

        self.assertIsInstance(track, Song)
        self.assertEqual(
            as_any(track).webpage_url, "https://youtube.test/watch?v=1"
        )
        self.assertIsInstance(playlist, Playlist)

    def test_get_soundcloud_info_accepts_http_mp3_track(self) -> None:
        ydl = MagicMock()
        ydl.extract_info.return_value = {
            "title": "SoundCloud Track",
            "url": "https://soundcloud.test/stream",
            "duration": 90,
            "view_count": 8,
            "formats": [{"format_id": "http_mp3_128"}],
        }

        with patch.object(resolver, "YoutubeDL", return_value=ydl_context(ydl)):
            result = self.audio_resolver.get_soundcloud_info(
                "https://soundcloud.com/miku/track"
            )

        self.assertIsInstance(result, Song)
        self.assertEqual(as_any(result).title, "SoundCloud Track")

    def test_download_errors_return_none(self) -> None:
        ydl = MagicMock()
        ydl.extract_info.side_effect = DownloadError("unavailable")

        with patch.object(resolver, "YoutubeDL", return_value=ydl_context(ydl)):
            self.assertIsNone(self.audio_resolver.search_query("missing"))

    def test_non_spotify_audio_source_is_resolved_without_network(self) -> None:
        song = Song(
            "Miku",
            "https://youtube.test/watch?v=1",
            "https://image.test/1.jpg",
            "60",
            "1",
        )
        ydl = MagicMock()
        ydl.extract_info.return_value = {"url": "https://audio.test/stream"}

        with patch.object(
            resolver, "YoutubeDL", return_value=ydl_context(ydl)
        ) as ydl_class:
            result = resolver._get_audio_source_impl(song)

        self.assertEqual(result, "https://audio.test/stream")
        ydl_class.assert_called_once_with(resolver.AUDIO_OPTS)
        ydl.extract_info.assert_called_once_with(
            url="https://youtube.test/watch?v=1", download=False
        )
