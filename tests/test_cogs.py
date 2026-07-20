from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import hatsune_miku_bot.cogs.debug as debug_module
import hatsune_miku_bot.cogs.music as music_module
import hatsune_miku_bot.cogs.utility as utility_module


def as_any(value: object) -> Any:
    return value


class FakeSession:
    def __init__(self, **_kwargs: object) -> None:
        self.closed = False
        self.close = AsyncMock(side_effect=self._close)

    async def _close(self) -> None:
        self.closed = True


class MusicCogTests(unittest.IsolatedAsyncioTestCase):
    async def test_cog_load_and_unload_manage_audio_session(self) -> None:
        cog = music_module.MikuMusicCommands(
            as_any(SimpleNamespace()), as_any(AsyncMock())
        )

        with (
            patch.object(music_module, "ClientSession", FakeSession),
            patch.object(music_module, "AudioInfoResolver") as resolver_class,
        ):
            await cog.cog_load()
            session = cog.audio_session
            self.assertIsNotNone(session)
            resolver_class.assert_called_once_with(session)
            await cog.cog_load()
            resolver_class.assert_called_once()
            await cog.cog_unload()

        self.assertIsNone(cog.audio_info_resolver)
        assert isinstance(session, FakeSession)
        session.close.assert_awaited_once_with()

    async def test_guild_join_and_remove_manage_controller(self) -> None:
        bot = as_any(SimpleNamespace())
        db_logic = as_any(AsyncMock())
        cog = music_module.MikuMusicCommands(bot, db_logic)
        guild = as_any(SimpleNamespace(id=42, name="Test Guild"))
        controller = SimpleNamespace(run=AsyncMock(), stop=AsyncMock())

        with patch.object(
            music_module, "GuildStateController", return_value=controller
        ) as controller_class:
            await cog.on_guild_join(guild)

        controller_class.assert_called_once_with(bot, 42, db_logic)
        controller.run.assert_awaited_once_with()
        self.assertIs(cog.guildstate_con_dict[42], controller)

        await cog.on_guild_remove(guild)

        controller.stop.assert_awaited_once_with()
        self.assertNotIn(42, cog.guildstate_con_dict)

    async def test_on_ready_initializes_each_guild_once(self) -> None:
        guilds = [
            SimpleNamespace(id=1, name="One"),
            SimpleNamespace(id=2, name="Two"),
        ]
        bot = as_any(SimpleNamespace(guilds=guilds))
        db_logic = as_any(AsyncMock())
        cog = music_module.MikuMusicCommands(bot, db_logic)
        controllers: list[SimpleNamespace] = []

        def controller_factory(
            _bot: object, guild_id: int, _db_logic: object
        ) -> SimpleNamespace:
            controller = SimpleNamespace(id=guild_id, run=AsyncMock())
            controllers.append(controller)
            return controller

        with patch.object(
            music_module,
            "GuildStateController",
            side_effect=controller_factory,
        ) as controller_class:
            await cog.on_ready()
            await cog.on_ready()

        self.assertTrue(cog.synced)
        self.assertEqual(controller_class.call_count, 2)
        for controller in controllers:
            controller.run.assert_awaited_once_with()

    async def test_play_delegates_resolved_song_to_guild_controller(
        self,
    ) -> None:
        class FakeTextChannel:
            pass

        class FakeVoiceClient:
            pass

        song = object()
        vc = FakeVoiceClient()
        interaction = SimpleNamespace(
            guild_id=42,
            channel=FakeTextChannel(),
            response=SimpleNamespace(defer=AsyncMock()),
        )
        resolver = SimpleNamespace(get_song_info=AsyncMock(return_value=song))
        controller = SimpleNamespace(
            queue_songs=AsyncMock(),
            begin_playback=AsyncMock(),
            add_event=AsyncMock(),
        )
        cog = music_module.MikuMusicCommands(
            as_any(SimpleNamespace()), as_any(AsyncMock())
        )
        cog.audio_info_resolver = as_any(resolver)
        cog.guildstate_con_dict[42] = as_any(controller)

        with (
            patch.object(music_module, "TextChannel", FakeTextChannel),
            patch.object(music_module, "VoiceClient", FakeVoiceClient),
            patch.object(
                music_module, "join_vc", new=AsyncMock(return_value=vc)
            ),
        ):
            await as_any(music_module.MikuMusicCommands.play.callback)(
                cog, interaction, "world is mine"
            )

        interaction.response.defer.assert_awaited_once_with()
        resolver.get_song_info.assert_awaited_once_with("world is mine")
        self.assertEqual(controller.add_event.await_count, 2)
        controller.add_event.assert_any_await(
            controller.queue_songs, interaction, song, vc
        )
        controller.add_event.assert_any_await(controller.begin_playback)


class UtilityCogTests(unittest.IsolatedAsyncioTestCase):
    async def test_die_replies_then_closes_bot(self) -> None:
        bot = SimpleNamespace(close=AsyncMock())
        cog = utility_module.UtilityCommands(as_any(bot))

        with patch.object(
            utility_module, "reply", new=AsyncMock()
        ) as reply_mock:
            await as_any(utility_module.UtilityCommands.die.callback)(
                cog, as_any(object())
            )

        reply_mock.assert_awaited_once()
        bot.close.assert_awaited_once_with()

    async def test_help_lists_application_commands(self) -> None:
        commands = [
            SimpleNamespace(name="play", description="Play a song"),
            SimpleNamespace(name="queue", description="Show queue"),
        ]
        bot = SimpleNamespace(
            tree=SimpleNamespace(walk_commands=Mock(return_value=commands))
        )
        cog = utility_module.UtilityCommands(as_any(bot))

        with (
            patch.object(
                utility_module, "reply", new=AsyncMock()
            ) as reply_mock,
            patch.object(
                utility_module, "gen_bot_thumbnail", return_value=object()
            ),
        ):
            await as_any(utility_module.UtilityCommands.help.callback)(
                cog, as_any(object())
            )

        self.assertIsNotNone(reply_mock.await_args)
        assert reply_mock.await_args is not None
        embed = reply_mock.await_args.kwargs["embed"]
        self.assertIn("play: Play a song", embed.fields[0].value)
        self.assertIn("queue: Show queue", embed.fields[0].value)


class DebugCogTests(unittest.IsolatedAsyncioTestCase):
    def test_command_embed_summarizes_cog(self) -> None:
        bot = SimpleNamespace()
        debugger = debug_module.BotDebugger(as_any(bot))
        command_cog = as_any(
            SimpleNamespace(__cog_app_commands__=[SimpleNamespace(name="play")])
        )

        commands_embed = debugger.return_commands_embed(command_cog)

        self.assertIn("play", str(commands_embed.fields[0].value))

    async def test_reload_cog_reloads_known_extension(self) -> None:
        bot = SimpleNamespace(
            extensions={"hatsune_miku_bot.cogs.music": object()},
            reload_extension=AsyncMock(),
        )
        debugger = debug_module.BotDebugger(as_any(bot))

        with patch.object(debug_module, "reply", new=AsyncMock()) as reply_mock:
            await as_any(debug_module.BotDebugger.reload_cog.callback)(
                debugger,
                object(),
                "hatsune_miku_bot.cogs.music",
            )

        bot.reload_extension.assert_awaited_once_with(
            "hatsune_miku_bot.cogs.music"
        )
        reply_mock.assert_awaited_once()
