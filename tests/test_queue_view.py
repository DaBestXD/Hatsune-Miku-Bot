from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

from hatsune_miku_bot.audio.guild_state_controller import GuildStateController
from hatsune_miku_bot.audio.queue_view import QueueEmbed, QueueView
from hatsune_miku_bot.audio.song_playlist_classes import Song


def as_any(value: object) -> Any:
    return value


def make_song(number: int) -> Song:
    return Song(
        f"Song {number}",
        f"https://song.test/{number}",
        "https://image.test/song.jpg",
        "60",
        str(number),
    )


def make_controller(song_count: int) -> GuildStateController:
    bot = as_any(SimpleNamespace(loop=asyncio.get_running_loop()))
    controller = GuildStateController(bot, 42)
    controller.state.songs = [make_song(index) for index in range(song_count)]
    controller.state.active_song = controller.state.songs[0]
    return controller


class QueueEmbedTests(unittest.IsolatedAsyncioTestCase):
    async def test_queue_embed_paginates_ten_queued_songs_per_page(
        self,
    ) -> None:
        controller = make_controller(13)
        queue_embed = QueueEmbed(controller)

        self.assertEqual(queue_embed.max_pages, 1)
        self.assertIsNotNone(queue_embed.embed)
        assert queue_embed.embed is not None
        self.assertEqual(queue_embed.embed.footer.text, "Page: 1 of 2")
        self.assertIn("1. [Song 1]", str(queue_embed.embed.fields[0].value))
        self.assertIn("10. [Song 10]", str(queue_embed.embed.fields[0].value))

        queue_embed.page_right(controller)

        self.assertEqual(queue_embed.page_number, 1)
        self.assertEqual(queue_embed.embed.footer.text, "Page: 2 of 2")
        self.assertIn("11. [Song 11]", str(queue_embed.embed.fields[0].value))
        self.assertIn("12. [Song 12]", str(queue_embed.embed.fields[0].value))

    async def test_page_bounds_are_clamped(self) -> None:
        controller = make_controller(2)
        queue_embed = QueueEmbed(controller)

        queue_embed.page_left(controller)
        self.assertEqual(queue_embed.page_number, 0)
        queue_embed.page_right(controller)
        self.assertEqual(queue_embed.page_number, 0)

    async def test_queue_view_initial_buttons_and_timeout(self) -> None:
        controller = make_controller(12)
        miku = SimpleNamespace(guildstate_con_dict={42: controller})
        view = QueueView(QueueEmbed(controller), as_any(miku), timeout=None)
        message = SimpleNamespace(edit=AsyncMock())
        view.message = message

        self.assertFalse(view.page_right.disabled)
        self.assertFalse(view.button_shuffle.disabled)

        await view.on_timeout()

        message.edit.assert_awaited_once_with(view=view)
        self.assertTrue(
            all(getattr(item, "disabled", False) for item in view.children)
        )
