from __future__ import annotations

import requests
import unittest
from unittest.mock import MagicMock, Mock, call, patch

import hatsune_miku_bot.audio_utils.audio_handler as audio_handler
from hatsune_miku_bot.audio_utils.audio_class import Song


class SpotifyRequestTests(unittest.TestCase):
    def test_spotify_request_retries_transient_statuses_then_returns_response(self) -> None:
        transient_1 = Mock(status_code=502)
        transient_2 = Mock(status_code=503)
        success = Mock(status_code=200)

        with (
            patch.object(
                audio_handler.requests,
                "request",
                side_effect=[transient_1, transient_2, success],
            ) as request_mock,
            patch.object(audio_handler.time, "sleep") as sleep_mock,
        ):
            response = audio_handler.spotify_request("get", "https://spotify.test/token")

        self.assertIs(response, success)
        self.assertEqual(request_mock.call_count, 3)
        self.assertEqual(
            sleep_mock.call_args_list,
            [call(0.5), call(1.0)],
        )
        self.assertTrue(
            all(
                request_call.kwargs["timeout"] == audio_handler.SPOTIFY_REQUEST_TIMEOUT_S
                for request_call in request_mock.call_args_list
            )
        )

    def test_spotify_request_returns_none_after_request_exceptions(self) -> None:
        with (
            patch.object(
                audio_handler.requests,
                "request",
                side_effect=[
                    requests.Timeout("first timeout"),
                    requests.Timeout("second timeout"),
                    requests.Timeout("third timeout"),
                ],
            ) as request_mock,
            patch.object(audio_handler.time, "sleep") as sleep_mock,
        ):
            response = audio_handler.spotify_request("get", "https://spotify.test/tracks")

        self.assertIsNone(response)
        self.assertEqual(request_mock.call_count, 3)
        self.assertEqual(sleep_mock.call_args_list, [call(0.5), call(1.0)])


class SpotifyInfoTests(unittest.TestCase):
    def test_get_spotify_info_returns_none_without_token(self) -> None:
        with (
            patch.object(audio_handler, "get_token", return_value=None) as get_token_mock,
            patch.object(audio_handler, "spotify_request") as spotify_request_mock,
        ):
            result = audio_handler.get_spotify_info(
                "https://open.spotify.com/track/test-id", "test-id"
            )

        self.assertIsNone(result)
        get_token_mock.assert_called_once_with()
        spotify_request_mock.assert_not_called()


class AudioSourceTests(unittest.TestCase):
    def _spotify_song(self) -> Song:
        return Song(
            "World is Mine - Hatsune Miku",
            "https://open.spotify.com/track/test-id",
            "https://thumb.test/image.jpg",
            "210",
            "0",
        )

    def _ydl_context(self, ydl_mock: MagicMock) -> MagicMock:
        context = MagicMock()
        context.__enter__.return_value = ydl_mock
        context.__exit__.return_value = None
        return context

    def test_get_audio_source_fuzzy_matches_spotify_tracks_before_resolving(
        self,
    ) -> None:
        spotify_song = self._spotify_song()
        fake_search_ydl = MagicMock()
        fake_search_ydl.extract_info.return_value = {
            "entries": [
                {
                    "title": "Unrelated Song",
                    "channel": "Wrong Artist",
                    "duration": 210,
                    "view_count": 10_000,
                    "url": "https://youtube.test/wrong",
                },
                {
                    "title": "Hatsune Miku - World is Mine",
                    "channel": "Hatsune Miku",
                    "duration": 211,
                    "view_count": 12,
                    "url": "https://youtube.test/correct",
                },
            ]
        }
        fake_resolve_ydl = MagicMock()
        fake_resolve_ydl.extract_info.return_value = {
            "url": "https://audio.test/resolved"
        }
        fake_ydl_cls = MagicMock()
        fake_ydl_cls.side_effect = [
            self._ydl_context(fake_search_ydl),
            self._ydl_context(fake_resolve_ydl),
        ]

        with patch.object(audio_handler, "YoutubeDL", fake_ydl_cls):
            result = audio_handler._get_Audio_Source(spotify_song)

        self.assertEqual(result, "https://audio.test/resolved")
        fake_ydl_cls.assert_has_calls(
            [call(audio_handler.SPOTIFY_SEARCH_OPTS), call(audio_handler.AUDIO_OPTS)]
        )
        fake_search_ydl.extract_info.assert_called_once_with(
            "ytsearch3:World is Mine - Hatsune Miku",
            download=False,
            process=False,
        )
        fake_resolve_ydl.extract_info.assert_called_once_with(
            url="https://youtube.test/correct",
            download=False,
        )

    def test_get_audio_source_uses_first_spotify_result_on_score_tie(self) -> None:
        spotify_song = self._spotify_song()
        fake_search_ydl = MagicMock()
        fake_search_ydl.extract_info.return_value = {
            "entries": [
                {
                    "title": "World is Mine first",
                    "channel": "Hatsune Miku",
                    "url": "https://youtube.test/first",
                },
                {
                    "title": "World is Mine second",
                    "channel": "Hatsune Miku",
                    "url": "https://youtube.test/second",
                },
            ]
        }
        fake_resolve_ydl = MagicMock()
        fake_resolve_ydl.extract_info.return_value = {"url": "https://audio.test/first"}
        fake_ydl_cls = MagicMock()
        fake_ydl_cls.side_effect = [
            self._ydl_context(fake_search_ydl),
            self._ydl_context(fake_resolve_ydl),
        ]

        with patch.object(audio_handler, "YoutubeDL", fake_ydl_cls):
            result = audio_handler._get_Audio_Source(spotify_song)

        self.assertEqual(result, "https://audio.test/first")
        fake_resolve_ydl.extract_info.assert_called_once_with(
            url="https://youtube.test/first",
            download=False,
        )

    def test_get_audio_source_returns_none_without_spotify_candidates(self) -> None:
        spotify_song = self._spotify_song()
        fake_search_ydl = MagicMock()
        fake_search_ydl.extract_info.return_value = {
            "entries": [
                {"title": "Missing URL", "channel": "Hatsune Miku"},
                "not a dict",
            ]
        }
        fake_ydl_cls = MagicMock(return_value=self._ydl_context(fake_search_ydl))

        with patch.object(audio_handler, "YoutubeDL", fake_ydl_cls):
            result = audio_handler._get_Audio_Source(spotify_song)

        self.assertIsNone(result)
        fake_ydl_cls.assert_called_once_with(audio_handler.SPOTIFY_SEARCH_OPTS)

    def test_get_audio_source_keeps_non_spotify_resolution_path(self) -> None:
        youtube_song = Song(
            "World is Mine",
            "https://youtube.test/watch?v=test-id",
            "https://thumb.test/image.jpg",
            "210",
            "0",
        )
        fake_ydl = MagicMock()
        fake_ydl.extract_info.return_value = {"url": "https://audio.test/youtube"}
        fake_ydl_cls = MagicMock(return_value=self._ydl_context(fake_ydl))

        with patch.object(audio_handler, "YoutubeDL", fake_ydl_cls):
            result = audio_handler._get_Audio_Source(youtube_song)

        self.assertEqual(result, "https://audio.test/youtube")
        fake_ydl_cls.assert_called_once_with(audio_handler.AUDIO_OPTS)
        fake_ydl.extract_info.assert_called_once_with(
            url="https://youtube.test/watch?v=test-id",
            download=False,
        )
