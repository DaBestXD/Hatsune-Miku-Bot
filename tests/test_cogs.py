from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import hatsune_miku_bot.cogs.debug as debug_module
import hatsune_miku_bot.cogs.music as music_module
import hatsune_miku_bot.cogs.utility as utility_module
from hatsune_miku_bot.audio.song_playlist_classes import Song


def as_any(value: object) -> Any:
    return value


class FakeSession:
    def __init__(self, **_kwargs: object) -> None:
        self.closed = False
        self.close = AsyncMock(side_effect=self._close)

    async def _close(self) -> None:
        self.closed = True


class MusicCogTests(unittest.IsolatedAsyncioTestCase):
    async def test_playlist_autocomplete_wrappers_filter_sort_and_limit(
        self,
    ) -> None:
        playlist_names = [
            "Unrelated",
            *[f"Miku Mix {index:02}" for index in reversed(range(30))],
        ]
        db_logic = SimpleNamespace(
            fetch_playlist_names=AsyncMock(return_value=playlist_names)
        )
        cog = music_module.MikuMusicCommands(
            as_any(SimpleNamespace()),
            as_any(db_logic),
        )
        interaction = as_any(SimpleNamespace(guild_id=42))

        autocomplete_callbacks = [
            cog.play_custom_playlist_autocomplete,
            cog.delete_custom_playlist_autocomplete,
        ]
        for callback in autocomplete_callbacks:
            with self.subTest(callback=callback.__name__):
                choices = await as_any(callback)(interaction, "MIKU")

                self.assertEqual(len(choices), 25)
                self.assertEqual(
                    [choice.name for choice in choices],
                    [f"Miku Mix {index:02}" for index in range(25)],
                )

        self.assertEqual(db_logic.fetch_playlist_names.await_count, 2)
        db_logic.fetch_playlist_names.assert_awaited_with(interaction)

    async def test_custom_playlist_add_resolves_song_and_remove_uses_url(
        self,
    ) -> None:
        song = Song(
            "Melt",
            "https://song.test/melt",
            "https://image.test/melt.jpg",
            "180",
            "39",
        )
        resolver = SimpleNamespace(get_song_info=AsyncMock(return_value=song))
        controller = SimpleNamespace(
            add_event=AsyncMock(),
            add_song_to_custom_playlist=AsyncMock(),
            remove_song_from_custom_playlist=AsyncMock(),
        )
        cog = music_module.MikuMusicCommands(
            as_any(SimpleNamespace()),
            as_any(AsyncMock()),
        )
        cog.audio_info_resolver = as_any(resolver)
        cog.guildstate_con_dict[42] = as_any(controller)
        commands = [
            (
                music_module.MikuMusicCommands.add_song_to_custom_playlist,
                controller.add_song_to_custom_playlist,
                "Melt",
                song,
            ),
            (
                music_module.MikuMusicCommands.remove_song_from_custom_playlist,
                controller.remove_song_from_custom_playlist,
                song.webpage_url,
                song.webpage_url,
            ),
        ]

        for (
            command,
            controller_method,
            supplied_value,
            expected_value,
        ) in commands:
            with self.subTest(command=command.name):
                interaction = SimpleNamespace(
                    guild_id=42,
                    response=SimpleNamespace(defer=AsyncMock()),
                )
                await as_any(command.callback)(
                    cog,
                    interaction,
                    "Miku Mix",
                    supplied_value,
                )

                interaction.response.defer.assert_awaited_once_with()
                controller.add_event.assert_awaited_once_with(
                    controller_method,
                    interaction,
                    "Miku Mix",
                    expected_value,
                )
                controller.add_event.reset_mock()

        resolver.get_song_info.assert_awaited_once_with("Melt")

    async def test_custom_playlist_remove_forwards_manual_title(self) -> None:
        controller = SimpleNamespace(
            add_event=AsyncMock(),
            remove_song_from_custom_playlist=AsyncMock(),
        )
        cog = music_module.MikuMusicCommands(
            as_any(SimpleNamespace()),
            as_any(AsyncMock()),
        )
        cog.guildstate_con_dict[42] = as_any(controller)
        interaction = SimpleNamespace(
            guild_id=42,
            response=SimpleNamespace(defer=AsyncMock()),
        )

        await as_any(
            music_module.MikuMusicCommands.remove_song_from_custom_playlist.callback
        )(
            cog,
            interaction,
            "Miku Mix",
            "Melt",
        )

        controller.add_event.assert_awaited_once_with(
            controller.remove_song_from_custom_playlist,
            interaction,
            "Miku Mix",
            "Melt",
        )

    async def test_custom_playlist_create_and_delete_enqueue_controller(
        self,
    ) -> None:
        controller = SimpleNamespace(
            add_event=AsyncMock(),
            create_custom_playlist=AsyncMock(),
            delete_custom_playlist=AsyncMock(),
        )
        cog = music_module.MikuMusicCommands(
            as_any(SimpleNamespace()),
            as_any(AsyncMock()),
        )
        cog.guildstate_con_dict[42] = as_any(controller)
        commands = [
            (
                music_module.MikuMusicCommands.create_custom_playlist,
                controller.create_custom_playlist,
            ),
            (
                music_module.MikuMusicCommands.delete_custom_playlist,
                controller.delete_custom_playlist,
            ),
        ]

        for command, controller_method in commands:
            with self.subTest(command=command.name):
                interaction = SimpleNamespace(
                    guild_id=42,
                    response=SimpleNamespace(defer=AsyncMock()),
                )
                await as_any(command.callback)(
                    cog,
                    interaction,
                    "Miku Mix",
                )

                interaction.response.defer.assert_awaited_once_with()
                controller.add_event.assert_awaited_once_with(
                    controller_method,
                    interaction,
                    "Miku Mix",
                )
                controller.add_event.reset_mock()

    async def test_custom_playlist_play_joins_and_enqueues_controller(
        self,
    ) -> None:
        class FakeVoiceClient:
            pass

        vc = FakeVoiceClient()
        interaction = SimpleNamespace(
            guild_id=42,
            response=SimpleNamespace(defer=AsyncMock()),
        )
        controller = SimpleNamespace(
            add_event=AsyncMock(),
            play_custom_playlist=AsyncMock(),
        )
        cog = music_module.MikuMusicCommands(
            as_any(SimpleNamespace()),
            as_any(AsyncMock()),
        )
        cog.guildstate_con_dict[42] = as_any(controller)

        with (
            patch.object(music_module, "VoiceClient", FakeVoiceClient),
            patch.object(
                music_module,
                "join_vc",
                new=AsyncMock(return_value=vc),
            ) as join_vc,
        ):
            await as_any(
                music_module.MikuMusicCommands.play_custom_playlist.callback
            )(
                cog,
                interaction,
                "Miku Mix",
            )

        interaction.response.defer.assert_awaited_once_with()
        join_vc.assert_awaited_once_with(interaction)
        controller.add_event.assert_awaited_once_with(
            controller.play_custom_playlist,
            interaction,
            "Miku Mix",
            vc,
        )

    def test_speed_command_declares_supported_range(self) -> None:
        parameters = music_module.MikuMusicCommands.speed.parameters

        self.assertEqual(len(parameters), 1)
        self.assertEqual(parameters[0].name, "effect_strength")
        self.assertEqual(parameters[0].min_value, 0.5)
        self.assertEqual(parameters[0].max_value, 2.0)

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

    async def test_cog_unload_completes_cleanup_after_controller_failure(
        self,
    ) -> None:
        cog = music_module.MikuMusicCommands(
            as_any(SimpleNamespace()), as_any(AsyncMock())
        )
        session = FakeSession()
        cog.audio_session = as_any(session)
        cog.audio_info_resolver = as_any(object())
        controllers = [
            SimpleNamespace(id=guild_id, stop=AsyncMock())
            for guild_id in (1, 2)
        ]
        controllers[0].stop.side_effect = RuntimeError("stop failed")
        cog.guildstate_con_dict = {
            controller.id: as_any(controller) for controller in controllers
        }

        with self.assertLogs(music_module.logger, level="ERROR"):
            await cog.cog_unload()

        self.assertEqual(cog.guildstate_con_dict, {})
        for controller in controllers:
            controller.stop.assert_awaited_once_with()
        session.close.assert_awaited_once_with()
        self.assertIsNone(cog.audio_info_resolver)

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

        controller_class.assert_called_once_with(
            bot,
            42,
            db_logic,
            cog.monitor,
        )
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
            _bot: object,
            guild_id: int,
            _db_logic: object,
            _monitor: object,
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

    async def test_voice_state_update_ignores_other_members(self) -> None:
        bot = SimpleNamespace(user=SimpleNamespace(id=10))
        cog = music_module.MikuMusicCommands(as_any(bot), as_any(AsyncMock()))
        original_vc = object()
        controller = SimpleNamespace(state=SimpleNamespace(vc=original_vc))
        cog.guildstate_con_dict[42] = as_any(controller)
        member = SimpleNamespace(
            id=11,
            guild=SimpleNamespace(id=42, name="Test Guild", voice_client=None),
        )

        await cog.on_voice_state_update(
            as_any(member),
            as_any(SimpleNamespace(channel=None)),
            as_any(SimpleNamespace(channel=object())),
        )

        self.assertIs(controller.state.vc, original_vc)

    async def test_voice_state_update_ignores_missing_controller(self) -> None:
        bot = SimpleNamespace(user=SimpleNamespace(id=10))
        cog = music_module.MikuMusicCommands(as_any(bot), as_any(AsyncMock()))
        member = SimpleNamespace(
            id=10,
            guild=SimpleNamespace(id=42, name="Test Guild", voice_client=None),
        )

        with self.assertLogs(music_module.logger, level="DEBUG"):
            await cog.on_voice_state_update(
                as_any(member),
                as_any(SimpleNamespace(channel=None)),
                as_any(SimpleNamespace(channel=object())),
            )

        self.assertEqual(cog.guildstate_con_dict, {})

    async def test_voice_state_update_tracks_bot_join_leave_and_move(
        self,
    ) -> None:
        class FakeVoiceClient:
            pass

        bot = SimpleNamespace(user=SimpleNamespace(id=10))
        cog = music_module.MikuMusicCommands(as_any(bot), as_any(AsyncMock()))
        voice_client = FakeVoiceClient()
        guild = SimpleNamespace(
            id=42, name="Test Guild", voice_client=voice_client
        )
        member = SimpleNamespace(id=10, guild=guild)
        controller = SimpleNamespace(state=SimpleNamespace(vc=None))
        cog.guildstate_con_dict[42] = as_any(controller)
        first_channel = object()
        second_channel = object()

        with patch.object(music_module, "VoiceClient", FakeVoiceClient):
            await cog.on_voice_state_update(
                as_any(member),
                as_any(SimpleNamespace(channel=None)),
                as_any(SimpleNamespace(channel=first_channel)),
            )
            self.assertIs(controller.state.vc, voice_client)

            controller.state.vc = None
            await cog.on_voice_state_update(
                as_any(member),
                as_any(SimpleNamespace(channel=first_channel)),
                as_any(SimpleNamespace(channel=second_channel)),
            )
            self.assertIs(controller.state.vc, voice_client)

            await cog.on_voice_state_update(
                as_any(member),
                as_any(SimpleNamespace(channel=second_channel)),
                as_any(SimpleNamespace(channel=None)),
            )
            self.assertIsNone(controller.state.vc)

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

    async def test_song_tracker_replies_when_no_songs_have_played(
        self,
    ) -> None:
        db_logic = SimpleNamespace(
            rank_song_per_guild=AsyncMock(return_value=[])
        )
        interaction = SimpleNamespace(
            guild_id=42,
            response=SimpleNamespace(defer=AsyncMock()),
        )
        cog = music_module.MikuMusicCommands(
            as_any(SimpleNamespace()), as_any(db_logic)
        )
        cog.guildstate_con_dict[42] = as_any(SimpleNamespace(db_logic=db_logic))

        with patch.object(music_module, "reply", new=AsyncMock()) as reply_mock:
            await as_any(music_module.MikuMusicCommands.song_tracker.callback)(
                cog, interaction
            )

        interaction.response.defer.assert_awaited_once_with()
        db_logic.rank_song_per_guild.assert_awaited_once_with(42)
        reply_mock.assert_awaited_once()
        self.assertIsNotNone(reply_mock.await_args)
        assert reply_mock.await_args is not None
        embed = reply_mock.await_args.kwargs["embed"]
        self.assertEqual(
            embed.author.name,
            "No songs played yet, go play some songs first!",
        )

    async def test_song_tracker_replies_with_ranked_songs(self) -> None:
        db_logic = SimpleNamespace(
            rank_song_per_guild=AsyncMock(
                return_value=[("World is Mine", 5), ("Melt", 3)]
            )
        )
        interaction = SimpleNamespace(
            guild_id=42,
            response=SimpleNamespace(defer=AsyncMock()),
        )
        cog = music_module.MikuMusicCommands(
            as_any(SimpleNamespace()), as_any(db_logic)
        )
        cog.guildstate_con_dict[42] = as_any(SimpleNamespace(db_logic=db_logic))

        with patch.object(music_module, "reply", new=AsyncMock()) as reply_mock:
            await as_any(music_module.MikuMusicCommands.song_tracker.callback)(
                cog, interaction
            )

        interaction.response.defer.assert_awaited_once_with()
        db_logic.rank_song_per_guild.assert_awaited_once_with(42)
        reply_mock.assert_awaited_once()
        self.assertIsNotNone(reply_mock.await_args)
        assert reply_mock.await_args is not None
        embed = reply_mock.await_args.kwargs["embed"]
        self.assertEqual(embed.fields[0].name, "Most songs played")
        self.assertEqual(
            embed.fields[0].value,
            "```\n1. World is Mine: 5 plays\n2. Melt: 3 plays\n```",
        )


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
