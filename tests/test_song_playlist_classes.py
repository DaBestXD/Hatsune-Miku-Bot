from __future__ import annotations

import unittest
from typing import Any

from hatsune_miku_bot.audio.song_playlist_classes import Playlist, Song


def as_any(value: object) -> Any:
    return value


def make_song(
    title: str = "World is Mine",
    url: str = "https://youtube.test/watch?v=1",
    duration: str = "180",
    views: str = "10",
) -> Song:
    return Song(title, url, "https://image.test/cover.jpg", duration, views)


class SongTests(unittest.TestCase):
    def test_duration_formatting_handles_short_long_and_invalid_values(
        self,
    ) -> None:
        short = make_song(duration="65.9")
        long = make_song(duration="3661")
        invalid = make_song(duration="unknown")

        self.assertEqual(
            (short.duration, short.formatted_duration), (65, "01:05")
        )
        self.assertEqual(
            (long.duration, long.formatted_duration), (3661, "01:01:01")
        )
        self.assertEqual(
            (invalid.duration, invalid.formatted_duration), (0, "0")
        )

    def test_from_spotify_builds_track_and_album_songs(self) -> None:
        response = {
            "name": "Melt",
            "duration_ms": 240_500,
            "artists": [{"name": "ryo"}],
            "external_urls": {"spotify": "https://open.spotify.test/track/1"},
            "album": {"images": [{"url": "https://image.test/track.jpg"}]},
        }

        track = Song.from_spotify(response, "")
        album_track = Song.from_spotify(
            response, "https://image.test/album.jpg"
        )

        self.assertEqual(track.title, "Melt - ryo")
        self.assertEqual(track.duration, 240)
        self.assertEqual(track.thumbnail_url, "https://image.test/track.jpg")
        self.assertEqual(
            album_track.thumbnail_url, "https://image.test/album.jpg"
        )

    def test_from_yt_dlp_uses_last_thumbnail(self) -> None:
        song = Song.from_yt_dlp(
            as_any(
                {
                    "title": "Tell Your World",
                    "url": "https://youtube.test/watch?v=2",
                    "duration": 250,
                    "view_count": 123,
                    "thumbnails": [
                        {"url": "https://image.test/small.jpg"},
                        {"url": "https://image.test/large.jpg"},
                    ],
                }
            )
        )

        self.assertEqual(song.thumbnail_url, "https://image.test/large.jpg")
        self.assertEqual(song.view_count, "123")

    def test_from_yt_dlp_direct_link_uses_original_url(self) -> None:
        song = Song.from_yt_dlp_direct_link(
            as_any(
                {
                    "title": "Tell Your World",
                    "url": None,
                    "original_url": "https://youtube.test/watch?v=2",
                    "duration": 250,
                    "view_count": 123,
                    "thumbnails": [
                        {"url": "https://image.test/small.jpg"},
                        {"url": "https://image.test/large.jpg"},
                    ],
                }
            )
        )

        self.assertEqual(song.webpage_url, "https://youtube.test/watch?v=2")
        self.assertEqual(song.thumbnail_url, "https://image.test/large.jpg")
        self.assertEqual(song.duration, 250)
        self.assertEqual(song.view_count, "123")

    def test_embeds_include_queue_and_skip_context(self) -> None:
        song = make_song(title="A" * 40)
        next_song = make_song(title="Next Song")

        playing = song.return_embed(next_song, queued=True, char_limit=10)
        skipped = song.return_skip_embed(next_song, char_limit=10)
        error = song.return_err_embed()

        self.assertEqual(playing.author.name, "Song added to queue:")
        self.assertEqual(playing.title, "AAAAAAAAAA...")
        self.assertEqual(playing.footer.text, "Next song: Next Song")
        self.assertEqual(skipped.author.name, "Skipping...")
        self.assertEqual(error.author.name, "Error trying to play:")


class PlaylistTests(unittest.TestCase):
    def test_playlist_supports_empty_songs_and_summarizes_duration(
        self,
    ) -> None:
        empty = Playlist([])

        self.assertEqual(empty.songs, [])
        self.assertEqual(empty.length, 0)
        self.assertEqual(empty.total_duration, 0)
        self.assertEqual(empty.formatted_duration, "00:00:00")

        playlist = Playlist(
            [make_song(duration="60"), make_song(duration="120")],
            playlist_title="Miku Mix",
        )

        self.assertEqual(playlist.length, 2)
        self.assertEqual(playlist.total_duration, 180)
        self.assertEqual(playlist.formatted_duration, "00:03:00")
        self.assertEqual(
            playlist.return_embed().author.name, "Added 2 songs to the queue"
        )

    def test_from_spotify_supports_playlist_and_album_payloads(self) -> None:
        metadata = {
            "name": "Collection",
            "images": [{"url": "https://image.test/collection.jpg"}],
        }
        song_json = {
            "name": "39 Music!",
            "duration_ms": 200_000,
            "artists": [{"name": "MikitoP"}],
            "external_urls": {"spotify": "https://open.spotify.test/track/39"},
            "album": {"images": [{"url": "https://image.test/song.jpg"}]},
        }

        playlist = Playlist.from_spotify(
            "https://open.spotify.test/playlist/1",
            metadata,
            {"items": [{"track": song_json}, {"track": None}]},
            is_album=False,
        )
        album = Playlist.from_spotify(
            "https://open.spotify.test/album/1",
            metadata,
            {"items": [song_json]},
            is_album=True,
        )

        self.assertEqual(len(playlist.songs), 1)
        self.assertEqual(
            playlist.songs[0].thumbnail_url, "https://image.test/song.jpg"
        )
        self.assertEqual(
            album.songs[0].thumbnail_url, "https://image.test/collection.jpg"
        )

    def test_from_yt_dlp_skips_empty_entries(self) -> None:
        playlist = Playlist.from_yt_dlp(
            as_any(
                {
                    "title": "YouTube Mix",
                    "original_url": "https://youtube.test/playlist?list=1",
                    "thumbnails": [{"url": "https://image.test/list.jpg"}],
                }
            ),
            as_any(
                [
                    {
                        "title": "Song One",
                        "url": "https://youtube.test/1",
                        "duration": 10,
                        "view_count": 1,
                    },
                    None,
                ]
            ),
        )

        self.assertEqual([song.title for song in playlist.songs], ["Song One"])
        self.assertEqual(
            playlist.playlist_thumbnail, "https://image.test/list.jpg"
        )

    def test_greatest_view_count_ignores_invalid_counts(self) -> None:
        low = make_song(title="Low", views="10")
        high = make_song(title="High", views="200")
        unknown = make_song(title="Unknown", views="None")

        playlist = Playlist([low, unknown, high])

        self.assertIs(playlist.greatest_view_count(), high)
        self.assertIsNone(Playlist([unknown]).greatest_view_count())
