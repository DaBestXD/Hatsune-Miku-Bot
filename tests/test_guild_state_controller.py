from __future__ import annotations

import asyncio
import io
import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import hatsune_miku_bot.audio.audio_resolver as resolver_module
import hatsune_miku_bot.audio.guild_state_controller as controller_module
import hatsune_miku_bot.audio.song_cache as song_cache_module
from hatsune_miku_bot.audio.guild_state_controller import (
    Event,
    GuildStateController,
    SongMods,
)
from hatsune_miku_bot.audio.song_cache import CachedSong
from hatsune_miku_bot.audio.song_playlist_classes import Playlist, Song


def as_any(value: object) -> Any:
    return value


def make_song(title: str, url: str) -> Song:
    return Song(title, url, "https://image.test/song.jpg", "180", "10")


def make_controller() -> GuildStateController:
    bot = as_any(SimpleNamespace(loop=asyncio.get_running_loop()))
    db_logic = as_any(
        SimpleNamespace(
            insert_song_playback=AsyncMock(),
            rank_song_per_guild=AsyncMock(return_value=[]),
        )
    )
    return GuildStateController(bot, 42, db_logic)


class FakeTextChannel:
    def __init__(self) -> None:
        self.send = AsyncMock()


class EventLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_is_idempotent_and_executes_queued_events(self) -> None:
        controller = make_controller()
        handled = asyncio.Event()

        async def handler(value: int) -> None:
            self.assertEqual(value, 39)
            handled.set()

        await controller.run()
        first_task = controller.task
        await controller.run()
        self.assertIs(controller.task, first_task)

        await controller.add_event(handler, 39)
        await asyncio.wait_for(handled.wait(), timeout=1)
        await asyncio.wait_for(controller.queue.join(), timeout=1)
        await controller.stop()
        await asyncio.wait_for(controller.queue.join(), timeout=1)

        self.assertIsNotNone(first_task)
        assert first_task is not None
        await asyncio.wait_for(first_task, timeout=1)

    async def test_main_loop_survives_a_failing_event(self) -> None:
        controller = make_controller()
        completed = asyncio.Event()

        async def failing() -> None:
            raise RuntimeError("event failed")

        async def succeeding() -> None:
            completed.set()

        await controller.run()
        await controller.add_event(failing)
        await controller.add_event(succeeding)
        await asyncio.wait_for(completed.wait(), timeout=1)
        task = controller.task
        await controller.stop()
        await asyncio.wait_for(controller.queue.join(), timeout=1)
        self.assertIsNone(controller.task)
        assert task is not None
        await task


class CacheAndQueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_song_cache_lazily_deletes_expired_entries(self) -> None:
        controller = make_controller()

        with patch.object(song_cache_module.time, "time", return_value=1000):
            cached_song = CachedSong(
                "https://googlevideo.test/audio?expire=1400"
            )
            await controller.song_cache.add_key("song", cached_song)
            self.assertEqual(
                await controller.song_cache.get("song"), cached_song.source
            )

        with patch.object(song_cache_module.time, "time", return_value=1101):
            self.assertIsNone(await controller.song_cache.get("song"))

        self.assertEqual(await controller.song_cache.get_size(), 0)

    async def test_cached_song_default_expiry_is_set_at_creation(self) -> None:
        controller = make_controller()

        with patch.object(song_cache_module.time, "time", return_value=1000):
            cached_song = CachedSong("https://audio.test/source")
            await controller.song_cache.add_key("song", cached_song)

        self.assertEqual(cached_song.expiry, 2800)
        with patch.object(song_cache_module.time, "time", return_value=2799):
            self.assertEqual(
                await controller.song_cache.get("song"), cached_song.source
            )
        with patch.object(song_cache_module.time, "time", return_value=2801):
            self.assertIsNone(await controller.song_cache.get("song"))

    async def test_cache_song_records_only_resolved_sources(self) -> None:
        controller = make_controller()
        good = make_song("Good", "https://song.test/good")
        bad = make_song("Bad", "https://song.test/bad")

        with patch.object(
            controller_module,
            "get_audio_source",
            new=AsyncMock(side_effect=["https://audio.test/good", None]),
        ):
            await controller.cache_song(good)
            await controller.cache_song(bad)

        self.assertEqual(
            await controller.song_cache.get(good.webpage_url),
            "https://audio.test/good",
        )
        self.assertIsNone(await controller.song_cache.get(bad.webpage_url))
        self.assertEqual(await controller.song_cache.get_size(), 1)

    async def test_delete_key_handles_present_and_missing_keys(
        self,
    ) -> None:
        controller = make_controller()
        await controller.song_cache.add_key("song", CachedSong("source"))

        await controller.song_cache.delete_key("song")
        await controller.song_cache.delete_key("song")

        self.assertIsNone(await controller.song_cache.get("song"))
        self.assertEqual(await controller.song_cache.get_size(), 0)

    async def test_queue_songs_adds_song_and_playlist_and_schedules_cache(
        self,
    ) -> None:
        controller = make_controller()
        channel = FakeTextChannel()
        interaction = as_any(SimpleNamespace(channel=channel))
        vc = as_any(SimpleNamespace())
        first = make_song("First", "https://song.test/1")
        second = make_song("Second", "https://song.test/2")

        with (
            patch.object(controller_module, "TextChannel", FakeTextChannel),
            patch.object(
                controller_module, "reply", new=AsyncMock()
            ) as reply_mock,
        ):
            await controller.queue_songs(interaction, first, vc)
            await controller.queue_songs(
                interaction,
                Playlist([second], playlist_title="List"),
                vc,
            )

        self.assertEqual(controller.state.songs, [first, second])
        self.assertIs(controller.state.vc, vc)
        self.assertIs(controller.state.text_channel, channel)
        self.assertEqual(reply_mock.await_count, 2)
        self.assertEqual(controller.queue.qsize(), 2)


class PlaybackTests(unittest.IsolatedAsyncioTestCase):
    async def test_begin_playback_uses_cache_and_starts_voice_client(
        self,
    ) -> None:
        controller = make_controller()
        song = make_song("Cached", "https://song.test/cached")
        built_source = SimpleNamespace(volume=1.0)
        channel = FakeTextChannel()
        vc = SimpleNamespace(
            is_playing=Mock(return_value=False),
            play=Mock(),
        )
        controller.state.songs = [song]
        await controller.song_cache.add_key(
            song.webpage_url,
            CachedSong("https://audio.test/cached"),
        )
        controller.state.text_channel = as_any(channel)
        controller.state.vc = as_any(vc)

        with (
            patch.object(
                controller_module.asyncio,
                "to_thread",
                new=AsyncMock(return_value=built_source),
            ) as to_thread,
            patch.object(
                controller_module.time, "monotonic", return_value=100.0
            ),
        ):
            await controller.begin_playback()

        self.assertIs(controller.state.active_song, song)
        self.assertIs(controller.state.source, built_source)
        self.assertEqual(controller.state.song_mods.start_timestamp, 100.0)
        vc.play.assert_called_once()
        self.assertIs(vc.play.call_args.args[0], built_source)
        self.assertTrue(callable(vc.play.call_args.kwargs["after"]))
        channel.send.assert_awaited_once()
        self.assertEqual(controller.queue.qsize(), 0)
        to_thread.assert_awaited_once()

    async def test_begin_playback_resolves_cache_miss(self) -> None:
        controller = make_controller()
        song = make_song("Fresh", "https://song.test/fresh")
        vc = SimpleNamespace(is_playing=Mock(return_value=False), play=Mock())
        controller.state.songs = [song]
        controller.state.vc = as_any(vc)
        source = "https://googlevideo.test/fresh"

        with (
            patch.object(
                controller_module,
                "get_audio_source",
                new=AsyncMock(return_value=source),
            ),
            patch.object(
                controller_module.asyncio,
                "to_thread",
                new=AsyncMock(return_value=SimpleNamespace(volume=1.0)),
            ),
        ):
            await controller.begin_playback()

        self.assertEqual(
            await controller.song_cache.get(song.webpage_url),
            source,
        )
        vc.play.assert_called_once()

    async def test_stale_cache_retry_does_not_announce_or_count_twice(
        self,
    ) -> None:
        controller = make_controller()
        song = make_song("Cached", "https://song.test/cached")
        channel = FakeTextChannel()
        vc = SimpleNamespace(
            is_playing=Mock(return_value=False),
            play=Mock(),
        )
        controller.state.songs = [song]
        controller.state.text_channel = as_any(channel)
        controller.state.vc = as_any(vc)
        await controller.song_cache.add_key(
            song.webpage_url,
            CachedSong("https://audio.test/stale"),
        )

        with (
            patch.object(
                controller_module,
                "get_audio_source",
                new=AsyncMock(return_value="https://audio.test/fresh"),
            ),
            patch.object(
                controller_module.asyncio,
                "to_thread",
                new=AsyncMock(return_value=SimpleNamespace(volume=1.0)),
            ),
        ):
            await controller.begin_playback()
            await controller.finished_playback("HTTP error 403 Forbidden")

            event = await controller.queue.get()
            assert isinstance(event, Event)
            await event.func_to_execute()
            controller.queue.task_done()

        self.assertEqual(vc.play.call_count, 2)
        channel.send.assert_awaited_once()
        as_any(
            controller.db_logic
        ).insert_song_playback.assert_awaited_once_with(song, controller.id)
        self.assertEqual(
            await controller.song_cache.get(song.webpage_url),
            "https://audio.test/fresh",
        )
        self.assertEqual(controller.queue.qsize(), 0)

    async def test_soundcloud_403_retry_resolves_stable_webpage_url(
        self,
    ) -> None:
        webpage_url = "https://soundcloud.com/miku/track"
        stale_media_url = "https://cf-media.sndcdn.test/stale"
        fresh_media_url = "https://cf-media.sndcdn.test/fresh"
        metadata_ydl = MagicMock()
        metadata_ydl.__enter__.return_value = metadata_ydl
        metadata_ydl.extract_info.return_value = {
            "title": "SoundCloud Track",
            "url": stale_media_url,
            "webpage_url": webpage_url,
            "duration": 90,
            "view_count": 8,
            "formats": [{"format_id": "http_mp3_128"}],
        }
        playback_ydl = MagicMock()
        playback_ydl.__enter__.return_value = playback_ydl
        playback_ydl.extract_info.return_value = {"url": fresh_media_url}
        audio_resolver = resolver_module.AudioInfoResolver(as_any(object()))

        with patch.object(
            resolver_module,
            "YoutubeDL",
            side_effect=[metadata_ydl, playback_ydl],
        ) as ydl_class:
            song = audio_resolver.get_soundcloud_info(webpage_url)
            self.assertIsInstance(song, Song)
            assert song is not None

            controller = make_controller()
            built_source = SimpleNamespace(volume=1.0)
            channel = FakeTextChannel()
            vc = SimpleNamespace(
                is_playing=Mock(return_value=False),
                play=Mock(),
            )
            controller.state.songs = [song]
            controller.state.text_channel = as_any(channel)
            controller.state.vc = as_any(vc)
            await controller.song_cache.add_key(
                song.webpage_url,
                CachedSong(stale_media_url),
            )
            self.assertEqual(
                await controller.song_cache.get(webpage_url), stale_media_url
            )

            with patch.object(
                controller_module,
                "build_audio",
                return_value=built_source,
            ) as build_audio:
                await controller.begin_playback()
                await controller.finished_playback("HTTP error 403 Forbidden")

                event = await controller.queue.get()
                assert isinstance(event, Event)
                await event.func_to_execute()
                controller.queue.task_done()

        self.assertEqual(song.webpage_url, webpage_url)
        self.assertEqual(
            ydl_class.call_args_list,
            [
                call(params=resolver_module.SOUNDCLOUD_INFO_PARAMS),
                call(resolver_module.SOUNDCLOUD_AUDIO_PARAMS),
            ],
        )
        metadata_ydl.extract_info.assert_called_once_with(
            webpage_url, download=False
        )
        playback_ydl.extract_info.assert_called_once_with(
            url=webpage_url, download=False
        )
        self.assertEqual(
            [args.args[1] for args in build_audio.call_args_list],
            [stale_media_url, fresh_media_url],
        )
        self.assertEqual(
            await controller.song_cache.get(webpage_url), fresh_media_url
        )
        self.assertEqual(vc.play.call_count, 2)
        channel.send.assert_awaited_once()

    async def test_begin_playback_skips_unresolvable_song(self) -> None:
        controller = make_controller()
        broken = make_song("Broken", "https://song.test/broken")
        next_song = make_song("Next", "https://song.test/next")
        channel = FakeTextChannel()
        controller.state.songs = [broken, next_song]
        controller.state.vc = as_any(
            SimpleNamespace(is_playing=Mock(return_value=False))
        )
        controller.state.text_channel = as_any(channel)

        with patch.object(
            controller_module,
            "get_audio_source",
            new=AsyncMock(return_value=None),
        ):
            await controller.begin_playback()

        self.assertEqual(controller.state.songs, [next_song])
        self.assertIs(controller.state.active_song, next_song)
        channel.send.assert_awaited_once()
        self.assertEqual(controller.queue.qsize(), 1)

    async def test_finished_playback_advances_or_loops_normal_completion(
        self,
    ) -> None:
        first = make_song("First", "https://song.test/1")
        second = make_song("Second", "https://song.test/2")

        controller = make_controller()
        controller.state.songs = [first, second]
        controller.state.active_song = first
        controller.state.song_mods.start_timestamp = 10.0
        controller.state.song_mods.position_offset_s = 20.0
        await controller.finished_playback("")

        self.assertEqual(controller.state.songs, [second])
        self.assertIs(controller.state.active_song, second)
        self.assertIsNone(controller.state.song_mods.start_timestamp)
        self.assertEqual(controller.state.song_mods.position_offset_s, 0)
        self.assertEqual(controller.queue.qsize(), 1)

        looping = make_controller()
        looping.state.songs = [first, second]
        looping.state.active_song = first
        looping.state.song_mods.song_loop = True
        await looping.finished_playback("")
        self.assertEqual(looping.state.songs, [first, second])
        self.assertIs(looping.state.active_song, first)

    async def test_finished_playback_rotates_loop_all_queue(self) -> None:
        first = make_song("First", "https://song.test/1")
        second = make_song("Second", "https://song.test/2")
        third = make_song("Third", "https://song.test/3")

        controller = make_controller()
        controller.state.songs = [first, second, third]
        controller.state.active_song = first
        controller.state.song_mods.song_loop_all = True

        await controller.finished_playback("")

        self.assertEqual(controller.state.songs, [second, third, first])
        self.assertIs(controller.state.active_song, second)
        self.assertEqual(controller.queue.qsize(), 1)

    async def test_finished_playback_recovers_stale_cached_source(
        self,
    ) -> None:
        for song_loop, song_loop_all in (
            (False, False),
            (True, False),
            (False, True),
        ):
            with self.subTest(song_loop=song_loop, song_loop_all=song_loop_all):
                first = make_song("First", "https://song.test/1")
                second = make_song("Second", "https://song.test/2")
                controller = make_controller()
                controller.state.songs = [first, second]
                controller.state.active_song = first
                await controller.song_cache.add_key(
                    first.webpage_url,
                    CachedSong("https://audio.test/stale"),
                )
                await controller.song_cache.add_key(
                    second.webpage_url,
                    CachedSong("https://audio.test/second"),
                )
                controller.state.song_mods.song_loop = song_loop
                controller.state.song_mods.song_loop_all = song_loop_all
                controller.state.song_mods.start_timestamp = 10.0
                controller.state.song_mods.position_offset_s = 20.0

                await controller.finished_playback("HTTP error 403 Forbidden")

                self.assertEqual(controller.state.songs, [first, second])
                self.assertIs(controller.state.active_song, first)
                self.assertIsNone(
                    await controller.song_cache.get(first.webpage_url)
                )
                self.assertEqual(
                    await controller.song_cache.get(second.webpage_url),
                    "https://audio.test/second",
                )
                self.assertEqual(await controller.song_cache.get_size(), 1)
                self.assertIsNone(controller.state.song_mods.start_timestamp)
                self.assertEqual(
                    controller.state.song_mods.position_offset_s, 0
                )
                self.assertEqual(controller.queue.qsize(), 1)


class QueueMutationTests(unittest.IsolatedAsyncioTestCase):
    async def test_skip_disables_loop_stops_voice_and_schedules_cache(
        self,
    ) -> None:
        controller = make_controller()
        first = make_song("First", "https://song.test/1")
        second = make_song("Second", "https://song.test/2")
        vc = SimpleNamespace(stop=Mock())
        controller.state.songs = [first, second]
        controller.state.active_song = first
        controller.state.song_mods.song_loop = True
        controller.state.vc = as_any(vc)

        with patch.object(
            controller_module, "reply", new=AsyncMock()
        ) as reply_mock:
            await controller.skip(as_any(object()))

        self.assertFalse(controller.state.song_mods.song_loop)
        vc.stop.assert_called_once_with()
        reply_mock.assert_awaited_once()
        self.assertEqual(controller.queue.qsize(), 1)

    async def test_stop_playback_resets_visible_state_and_keeps_cache(
        self,
    ) -> None:
        controller = make_controller()
        song = make_song("First", "https://song.test/1")
        vc = SimpleNamespace(
            is_playing=Mock(return_value=True),
            stop=Mock(),
            disconnect=AsyncMock(),
        )
        controller.state.songs = [song]
        controller.state.active_song = song
        controller.state.text_channel = as_any(FakeTextChannel())
        controller.state.vc = as_any(vc)
        await controller.song_cache.add_key(
            song.webpage_url, CachedSong("cached")
        )
        controller.state.source = as_any(SimpleNamespace(volume=1.0))
        controller.state.song_mods.volume = 0.5
        controller.state.song_mods.song_loop = True

        with patch.object(
            controller_module, "reply", new=AsyncMock()
        ) as reply_mock:
            await controller.stop_playback(as_any(object()))

        self.assertEqual(controller.state.songs, [])
        self.assertIsNone(controller.state.active_song)
        self.assertIsNone(controller.state.text_channel)
        self.assertIsNone(controller.state.vc)
        self.assertIsNone(controller.state.source)
        self.assertEqual(
            await controller.song_cache.get(song.webpage_url), "cached"
        )
        self.assertEqual(await controller.song_cache.get_size(), 1)
        self.assertEqual(controller.state.song_mods.volume, 1.0)
        self.assertFalse(controller.state.song_mods.song_loop)
        vc.stop.assert_called_once_with()
        vc.disconnect.assert_awaited_once_with()
        reply_mock.assert_awaited_once()

    async def test_shuffle_preserves_active_song(self) -> None:
        controller = make_controller()
        first = make_song("First", "https://song.test/1")
        second = make_song("Second", "https://song.test/2")
        third = make_song("Third", "https://song.test/3")
        controller.state.songs = [first, second, third]

        def reverse(items: list[Song]) -> None:
            items.reverse()

        with (
            patch.object(controller_module, "reply", new=AsyncMock()),
            patch.object(
                controller_module.random, "shuffle", side_effect=reverse
            ),
        ):
            await controller.shuffle(as_any(object()))

        self.assertEqual(controller.state.songs, [first, third, second])
        self.assertEqual(controller.queue.qsize(), 1)

    async def test_volume_clear_loop_and_remove_mutate_queue(self) -> None:
        controller = make_controller()
        first = make_song("First", "https://song.test/1")
        second = make_song("Second", "https://song.test/2")
        third = make_song("Third", "https://song.test/3")
        source = SimpleNamespace(volume=1.0)
        controller.state.songs = [first, second, third]
        controller.state.active_song = first
        controller.state.source = as_any(source)

        with patch.object(
            controller_module, "reply", new=AsyncMock()
        ) as reply_mock:
            await controller.change_volume(0.25)
            await controller.remove_from_queue(as_any(object()), -1)
            await controller.remove_from_queue(as_any(object()), 1)
            await controller.remove_from_queue(as_any(object()), 0)
            await controller.loop_song(as_any(object()))
            await controller.loop_all(as_any(object()))
            await controller.loop_song(as_any(object()))
            await controller.clear_queue(as_any(object()))

        self.assertEqual(source.volume, 0.25)
        self.assertEqual(controller.state.songs, [first])
        self.assertTrue(controller.state.song_mods.song_loop)
        self.assertFalse(controller.state.song_mods.song_loop_all)
        self.assertEqual(reply_mock.await_count, 7)


class SongModificationTests(unittest.IsolatedAsyncioTestCase):
    def test_song_mods_build_filters_and_track_cumulative_position(
        self,
    ) -> None:
        mods = SongMods()
        mods.song_bass = 10
        mods.song_speed = 1.5
        mods.song_pitch = 1.25
        mods.start_timestamp = 100.0
        mods.position_offset_s = 30.0

        with patch.object(
            controller_module.time, "monotonic", return_value=110.0
        ):
            position = mods.interrupt_time()

        self.assertAlmostEqual(mods.effective_playback_rate, 1.875)
        self.assertAlmostEqual(position, 48.75)
        self.assertTrue(mods.is_nightcore())
        self.assertTrue(mods.is_song_mods_on)
        self.assertEqual(
            mods.combined_song_mods,
            ",bass=g=10,atempo=1.5,aresample=48000,"
            "asetrate=48000*1.25,aresample=48000",
        )

    async def test_nightcore_bass_and_speed_snapshot_and_restart_song(
        self,
    ) -> None:
        controller = make_controller()
        song = make_song("First", "https://song.test/1")
        vc = SimpleNamespace(stop=Mock())
        controller.state.songs = [song]
        controller.state.active_song = song
        controller.state.vc = as_any(vc)
        controller.state.song_mods.start_timestamp = 100.0

        with (
            patch.object(controller_module, "reply", new=AsyncMock()),
            patch.object(
                controller_module.time, "monotonic", return_value=110.0
            ),
        ):
            await controller.add_event(controller.nightcore, as_any(object()))
            await controller.add_event(
                controller.set_bass, as_any(object()), 8.0
            )
            await controller.add_event(
                controller.set_speed, as_any(object()), 1.5
            )
            for _ in range(3):
                event = await controller.queue.get()
                assert isinstance(event, Event)
                await event.func_to_execute()
                controller.queue.task_done()

        self.assertEqual(controller.state.song_mods.song_pitch, 1.25)
        self.assertEqual(controller.state.song_mods.song_bass, 8.0)
        self.assertEqual(controller.state.song_mods.song_speed, 1.5)
        self.assertTrue(controller.state.song_mods.modifier_restart_pending)
        self.assertEqual(controller.state.song_mods.position_offset_s, 10.0)
        self.assertEqual(controller.state.songs, [song])
        vc.stop.assert_called_once_with()

        await controller.finished_playback("")

        self.assertEqual(controller.state.songs, [song])
        self.assertEqual(controller.queue.qsize(), 1)

    async def test_effect_restart_does_not_mutate_looping_queue(
        self,
    ) -> None:
        for loop_attribute in ("song_loop", "song_loop_all"):
            with self.subTest(loop_attribute=loop_attribute):
                controller = make_controller()
                first = make_song("First", "https://song.test/1")
                second = make_song("Second", "https://song.test/2")
                vc = SimpleNamespace(stop=Mock())
                controller.state.songs = [first, second]
                controller.state.active_song = first
                controller.state.vc = as_any(vc)
                setattr(controller.state.song_mods, loop_attribute, True)
                controller.state.song_mods.start_timestamp = 100.0

                with (
                    patch.object(controller_module, "reply", new=AsyncMock()),
                    patch.object(
                        controller_module.time,
                        "monotonic",
                        return_value=110.0,
                    ),
                ):
                    await controller.nightcore(as_any(object()))

                await controller.finished_playback("")

                self.assertEqual(controller.state.songs, [first, second])
                self.assertIs(controller.state.active_song, first)
                self.assertEqual(controller.state.songs.count(first), 1)
                vc.stop.assert_called_once_with()
                self.assertEqual(controller.queue.qsize(), 1)

    async def test_song_effect_restart_is_not_logged_as_new_playback(
        self,
    ) -> None:
        controller = make_controller()
        song = make_song("First", "https://song.test/1")
        built_source = SimpleNamespace(volume=1.0)
        vc = SimpleNamespace(
            stop=Mock(), is_playing=Mock(return_value=False), play=Mock()
        )
        controller.state.songs = [song]
        controller.state.active_song = song
        controller.state.vc = as_any(vc)
        controller.state.song_mods.start_timestamp = 100.0
        await controller.song_cache.add_key(
            song.webpage_url, CachedSong("https://audio.test/1")
        )

        with (
            patch.object(controller_module, "reply", new=AsyncMock()),
            patch.object(
                controller_module.time, "monotonic", return_value=110.0
            ),
            patch.object(
                controller_module.asyncio,
                "to_thread",
                new=AsyncMock(return_value=built_source),
            ),
        ):
            await controller.nightcore(as_any(object()))
            await controller.finished_playback("")
            event = await controller.queue.get()
            assert isinstance(event, Event)
            await event.func_to_execute()
            controller.queue.task_done()

        self.assertFalse(controller.state.song_mods.modifier_restart_pending)
        as_any(controller.db_logic).insert_song_playback.assert_not_awaited()
        self.assertEqual(controller.state.songs, [song])
        vc.stop.assert_called_once_with()
        vc.play.assert_called_once()
        self.assertEqual(controller.queue.qsize(), 0)

    async def test_modified_restart_403_preserves_captured_position(
        self,
    ) -> None:
        controller = make_controller()
        first = make_song("First", "https://song.test/1")
        second = make_song("Second", "https://song.test/2")
        channel = FakeTextChannel()
        built_source = SimpleNamespace(volume=1.0)
        vc = SimpleNamespace(
            stop=Mock(), is_playing=Mock(return_value=False), play=Mock()
        )
        controller.state.songs = [first, second]
        controller.state.active_song = first
        controller.state.text_channel = as_any(channel)
        controller.state.vc = as_any(vc)
        controller.state.song_mods.start_timestamp = 100.0
        await controller.song_cache.add_key(
            first.webpage_url, CachedSong("https://audio.test/stale")
        )

        with (
            patch.object(controller_module, "reply", new=AsyncMock()),
            patch.object(
                controller_module.time, "monotonic", return_value=110.0
            ),
            patch.object(
                controller_module,
                "get_audio_source",
                new=AsyncMock(return_value="https://audio.test/fresh"),
            ) as get_audio_source,
            patch.object(
                controller_module.asyncio,
                "to_thread",
                new=AsyncMock(return_value=built_source),
            ) as to_thread,
        ):
            await controller.set_speed(as_any(object()), 1.5)
            await controller.finished_playback("")

            event = await controller.queue.get()
            assert isinstance(event, Event)
            await event.func_to_execute()
            controller.queue.task_done()

            self.assertFalse(
                controller.state.song_mods.modifier_restart_pending
            )
            self.assertEqual(controller.state.songs, [first, second])
            self.assertEqual(controller.state.song_mods.position_offset_s, 10.0)
            self.assertEqual(
                await controller.song_cache.get(first.webpage_url),
                "https://audio.test/stale",
            )
            get_audio_source.assert_not_awaited()

            stderr_buff = to_thread.await_args_list[0].args[3]
            assert isinstance(stderr_buff, io.BytesIO)
            stderr_buff.write(b"HTTP error 403 Forbidden")
            after_callback = vc.play.call_args.kwargs["after"]
            after_callback(None)

            completion_event = await asyncio.wait_for(
                controller.queue.get(), timeout=1
            )
            assert isinstance(completion_event, Event)
            await completion_event.func_to_execute()
            controller.queue.task_done()

            event = await controller.queue.get()
            assert isinstance(event, Event)
            await event.func_to_execute()
            controller.queue.task_done()

        self.assertEqual(controller.state.songs, [first, second])
        self.assertEqual(controller.state.songs.count(first), 1)
        self.assertEqual(
            await controller.song_cache.get(first.webpage_url),
            "https://audio.test/fresh",
        )
        self.assertFalse(controller.state.song_mods.modifier_restart_pending)
        as_any(controller.db_logic).insert_song_playback.assert_not_awaited()
        channel.send.assert_not_awaited()
        get_audio_source.assert_awaited_once_with(first)
        vc.stop.assert_called_once_with()
        self.assertEqual(vc.play.call_count, 2)
        self.assertEqual(controller.queue.qsize(), 0)
