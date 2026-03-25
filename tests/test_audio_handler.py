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
    def test_get_audio_source_uses_youtube_music_results_for_spotify_tracks(self) -> None:
        spotify_song = Song(
            "World is Mine",
            "https://open.spotify.com/track/test-id",
            "https://thumb.test/image.jpg",
            "210",
            "0",
        )
        fake_ydl = MagicMock()
        fake_ydl.extract_info.return_value = {
            "entries": [
                {"view_count": 12, "url": "https://audio.test/low"},
                {"view_count": 100, "url": "https://audio.test/high"},
            ]
        }
        fake_ydl_cls = MagicMock()
        fake_ydl_cls.return_value.__enter__.return_value = fake_ydl
        fake_ydl_cls.return_value.__exit__.return_value = None

        with patch.object(audio_handler, "YoutubeDL", fake_ydl_cls):
            result = audio_handler._get_Audio_Source(spotify_song)

        self.assertEqual(result, "https://audio.test/high")
        fake_ydl.extract_info.assert_called_once_with(
            "https://music.youtube.com/search?q=World+is+Mine#songs",
            download=False,
        )
