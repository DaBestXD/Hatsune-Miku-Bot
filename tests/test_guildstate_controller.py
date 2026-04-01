from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from audio_utils.audio_class import Song
from audio_utils.guildstate_controller import GuildStateController
from botextras.bot_events import (
    FinishedPlayback,
    QueueSongs,
    StopPlayblack,
)


def make_song(title: str, url: str) -> Song:
    return Song(title, url, "https://thumb.test/image.jpg", "180", "10")


class GuildStateControllerTests(unittest.IsolatedAsyncioTestCase):
    async def test_handle_queue_songs_sets_active_song_and_starts_playback(self) -> None:
        bot = SimpleNamespace(loop=asyncio.get_running_loop())
        controller = GuildStateController(bot, 42)
        song_1 = make_song("Song One", "https://song.test/1")
        song_2 = make_song("Song Two", "https://song.test/2")
        interaction = object()
        text_channel = SimpleNamespace(send=AsyncMock())
        vc = SimpleNamespace(is_playing=Mock(return_value=False))
        event = QueueSongs(
            songs=[song_1, song_2],
            vc=vc,
            text_channel=text_channel,
            interaction=interaction,
        )

        with (
            patch(
                "audio_utils.guildstate_controller.reply",
                new=AsyncMock(),
            ) as reply_mock,
            patch.object(controller, "_play", new=AsyncMock()) as play_mock,
        ):
            await controller._handle_queue_songs(event)

        self.assertEqual(controller.state.songs, [song_1, song_2])
        self.assertIs(controller.state.active_song, song_1)
        self.assertIs(controller.state.vc, vc)
        self.assertIs(controller.state.text_channel, text_channel)
        reply_mock.assert_awaited_once()
        play_mock.assert_awaited_once_with()

    async def test_play_skips_unplayable_song_and_advances_to_next_song(self) -> None:
        bot = SimpleNamespace(loop=asyncio.get_running_loop())
        controller = GuildStateController(bot, 42)
        first_song = make_song("Broken", "https://song.test/broken")
        second_song = make_song("Working", "https://song.test/working")
        built_source = object()
        text_channel = SimpleNamespace(send=AsyncMock())
        vc = SimpleNamespace(play=Mock(), is_playing=Mock(return_value=False))
        controller.state.songs = [first_song, second_song]
        controller.state.active_song = first_song
        controller.state.vc = vc
        controller.state.text_channel = text_channel

        with (
            patch(
                "audio_utils.guildstate_controller.get_Audio_Source",
                new=AsyncMock(side_effect=[None, "https://audio.test/stream"]),
            ) as get_audio_mock,
            patch.object(controller, "bad_cache", new=AsyncMock()) as bad_cache_mock,
            patch(
                "audio_utils.guildstate_controller.asyncio.to_thread",
                new=AsyncMock(return_value=built_source),
            ) as to_thread_mock,
        ):
            await controller._play()

        self.assertEqual(controller.state.songs, [second_song])
        self.assertIs(controller.state.active_song, second_song)
        self.assertIs(controller.state.source, built_source)
        self.assertEqual(get_audio_mock.await_count, 2)
        text_channel.send.assert_awaited()
        vc.play.assert_called_once()
        self.assertIs(vc.play.call_args.args[0], built_source)
        self.assertTrue(callable(vc.play.call_args.kwargs["after"]))
        to_thread_mock.assert_awaited_once()
        bad_cache_mock.assert_awaited_once_with()

    async def test_finished_playback_removes_current_song_and_recovers_from_403(self) -> None:
        bot = SimpleNamespace(loop=asyncio.get_running_loop())
        controller = GuildStateController(bot, 42)
        first_song = make_song("Song One", "https://song.test/1")
        second_song = make_song("Song Two", "https://song.test/2")
        controller.state.songs = [first_song, second_song]
        controller.state.active_song = first_song
        controller.state.song_cache[first_song.webpage_url] = "cached-source"

        with patch.object(controller, "_play", new=AsyncMock()) as play_mock:
            await controller._finished_playback(FinishedPlayback("403 Forbidden"))

        self.assertEqual(controller.state.songs, [second_song])
        self.assertIs(controller.state.active_song, second_song)
        self.assertNotIn(first_song.webpage_url, controller.state.song_cache)
        play_mock.assert_awaited_once_with()

    async def test_song_mod_helper_uses_rate_adjusted_song_position(self) -> None:
        bot = SimpleNamespace(loop=asyncio.get_running_loop())
        controller = GuildStateController(bot, 42)
        song = make_song("Song One", "https://song.test/1")
        voice_client = SimpleNamespace(stop=Mock())
        controller.state.active_song = song
        controller.state.songs = [song]
        controller.state.vc = voice_client
        controller.state.start_time = 100.0
        controller.state.position_offset_s = 30.0
        controller.state.song_speed = ",atempo=1.5"
        controller.state.nightcore = True

        with (
            patch(
                "audio_utils.guildstate_controller.reply",
                new=AsyncMock(),
            ) as reply_mock,
            patch(
                "audio_utils.guildstate_controller.time.monotonic",
                return_value=110.0,
            ),
        ):
            await controller._song_mod_helper(object(), "Bass set!")

        self.assertEqual(controller.state.songs, [song, song])
        self.assertAlmostEqual(controller.state.seek_time or 0.0, 48.75)
        voice_client.stop.assert_called_once_with()
        reply_mock.assert_awaited_once()

    async def test_setspeed_snapshots_position_before_updating_rate(self) -> None:
        from botextras.bot_events import SetSpeed as RuntimeSetSpeed

        bot = SimpleNamespace(loop=asyncio.get_running_loop())
        controller = GuildStateController(bot, 42)
        song = make_song("Song One", "https://song.test/1")
        controller.state.active_song = song
        controller.state.songs = [song]
        controller.state.start_time = 100.0
        controller.state.position_offset_s = 30.0
        controller.state.song_speed = ",atempo=1.5"

        with (
            patch(
                "audio_utils.guildstate_controller.mod_song",
                new=AsyncMock(return_value=",atempo=2.0"),
            ),
            patch(
                "audio_utils.guildstate_controller.time.monotonic",
                return_value=110.0,
            ),
            patch.object(controller, "_song_mod_helper", new=AsyncMock()) as helper_mock,
        ):
            await controller._setspeed(RuntimeSetSpeed(object(), object(), 2.0))

        self.assertEqual(controller.state.song_speed, ",atempo=2.0")
        self.assertTrue(controller.state.mod_song)
        helper_mock.assert_awaited_once()
        self.assertEqual(helper_mock.await_args.args[2], 45.0)

    async def test_stop_playback_resets_state_and_disconnects_voice_client(self) -> None:
        bot = SimpleNamespace(loop=asyncio.get_running_loop())
        controller = GuildStateController(bot, 42)
        song = make_song("Song One", "https://song.test/1")
        voice_client = SimpleNamespace(
            is_playing=Mock(return_value=True),
            stop=Mock(),
            disconnect=AsyncMock(),
        )
        controller.state.active_song = song
        controller.state.songs = [song]
        controller.state.position_offset_s = 20.0
        controller.state.seek_time = 15.0
        controller.state.text_channel = object()
        controller.state.start_time = 10.0
        controller.state.source = object()
        controller.state.nightcore = True
        controller.state.song_loop = True
        controller.state.mod_song = True
        controller.state.song_pitch = "pitch"
        controller.state.song_bass = "bass"
        controller.state.song_speed = "speed"
        controller.state.vc = voice_client

        with patch(
            "audio_utils.guildstate_controller.reply",
            new=AsyncMock(),
        ) as reply_mock:
            await controller._stop_playback(StopPlayblack(object()))

        self.assertIsNone(controller.state.active_song)
        self.assertEqual(controller.state.songs, [])
        self.assertEqual(controller.state.position_offset_s, 0.0)
        self.assertIsNone(controller.state.seek_time)
        self.assertIsNone(controller.state.text_channel)
        self.assertIsNone(controller.state.start_time)
        self.assertIsNone(controller.state.source)
        self.assertFalse(controller.state.nightcore)
        self.assertFalse(controller.state.song_loop)
        self.assertFalse(controller.state.mod_song)
        self.assertEqual(controller.state.song_pitch, "")
        self.assertEqual(controller.state.song_bass, "")
        self.assertEqual(controller.state.song_speed, "")
        self.assertIsNone(controller.state.vc)
        voice_client.stop.assert_called_once_with()
        voice_client.disconnect.assert_awaited_once_with()
        reply_mock.assert_awaited_once()

    async def test_hard_reset_stops_existing_task_disconnects_and_restarts_loop(self) -> None:
        bot = SimpleNamespace(loop=asyncio.get_running_loop())
        controller = GuildStateController(bot, 42)
        original_queue = controller.queue
        original_state = controller.state
        controller.task = asyncio.create_task(asyncio.sleep(10))
        voice_client = SimpleNamespace(
            is_playing=Mock(return_value=True),
            stop=Mock(),
            disconnect=AsyncMock(),
        )
        controller.state.vc = voice_client

        await controller.hard_reset()

        self.assertIsNotNone(controller.task)
        assert controller.task is not None
        self.assertFalse(controller.task.done())
        self.assertIsNot(controller.queue, original_queue)
        self.assertIsNot(controller.state, original_state)
        self.assertTrue(controller.queue.empty())
        self.assertEqual(controller.state.songs, [])
        voice_client.stop.assert_called_once_with()
        voice_client.disconnect.assert_awaited_once_with()
        await controller.stop()
