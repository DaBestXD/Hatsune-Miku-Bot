from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import hatsune_miku_bot.audio.guild_state_controller as controller_module
from hatsune_miku_bot.audio.guild_state_controller import (
    GuildStateController,
    SongMods,
    _song_mod_to_ffmpeg_str,
)
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
            controller.state.song_cache,
            {good.webpage_url: "https://audio.test/good"},
        )

    async def test_remove_song_from_cache_handles_present_and_missing_keys(
        self,
    ) -> None:
        controller = make_controller()
        controller.state.song_cache["song"] = "source"

        await controller.remove_song_from_cache("song")
        await controller.remove_song_from_cache("song")

        self.assertEqual(controller.state.song_cache, {})

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
        controller.state.song_cache[song.webpage_url] = (
            "https://audio.test/cached"
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
        self.assertEqual(controller.queue.qsize(), 1)
        to_thread.assert_awaited_once()

    async def test_begin_playback_resolves_cache_miss(self) -> None:
        controller = make_controller()
        song = make_song("Fresh", "https://song.test/fresh")
        vc = SimpleNamespace(is_playing=Mock(return_value=False), play=Mock())
        controller.state.songs = [song]
        controller.state.vc = as_any(vc)

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

        self.assertEqual(
            controller.state.song_cache[song.webpage_url],
            "https://audio.test/fresh",
        )
        vc.play.assert_called_once()

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
                controller.state.song_cache = {
                    first.webpage_url: "https://audio.test/stale",
                    second.webpage_url: "https://audio.test/second",
                }
                controller.state.song_mods.song_loop = song_loop
                controller.state.song_mods.song_loop_all = song_loop_all
                controller.state.song_mods.start_timestamp = 10.0
                controller.state.song_mods.position_offset_s = 20.0

                await controller.finished_playback("HTTP error 403 Forbidden")

                self.assertEqual(controller.state.songs, [first, second])
                self.assertIs(controller.state.active_song, first)
                self.assertNotIn(first.webpage_url, controller.state.song_cache)
                self.assertEqual(
                    controller.state.song_cache,
                    {second.webpage_url: "https://audio.test/second"},
                )
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
        controller.state.song_cache[song.webpage_url] = "cached"
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
            controller.state.song_cache, {song.webpage_url: "cached"}
        )
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
        self.assertEqual(_song_mod_to_ffmpeg_str("off", 0), "")

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
            await controller.nightcore(as_any(object()))
            await controller.set_bass(as_any(object()), 8.0)
            await controller.set_speed(as_any(object()), 1.5)

        self.assertEqual(controller.state.song_mods.song_pitch, 1.25)
        self.assertEqual(controller.state.song_mods.song_bass, 8.0)
        self.assertEqual(controller.state.song_mods.song_speed, 1.5)
        self.assertTrue(controller.state.song_mods.is_song_modified)
        self.assertEqual(controller.state.songs.count(song), 4)
        self.assertEqual(vc.stop.call_count, 3)

    async def test_song_effect_restart_is_not_logged_as_new_playback(
        self,
    ) -> None:
        controller = make_controller()
        song = make_song("First", "https://song.test/1")
        built_source = SimpleNamespace(volume=1.0)
        vc = SimpleNamespace(is_playing=Mock(return_value=False), play=Mock())
        controller.state.songs = [song]
        controller.state.vc = as_any(vc)
        controller.state.song_cache[song.webpage_url] = "https://audio.test/1"
        controller.state.song_mods.is_song_modified = True

        with patch.object(
            controller_module.asyncio,
            "to_thread",
            new=AsyncMock(return_value=built_source),
        ):
            await controller.begin_playback()

        self.assertFalse(controller.state.song_mods.is_song_modified)
        as_any(controller.db_logic).insert_song_playback.assert_not_awaited()
        self.assertEqual(controller.queue.qsize(), 0)
