from __future__ import annotations

import io
import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import discord

import hatsune_miku_bot.audio.playback_helpers as playback
import hatsune_miku_bot.utils.discord_helpers as helpers


def as_any(value: object) -> Any:
    return value


class PlaybackHelperTests(unittest.IsolatedAsyncioTestCase):
    def test_build_audio_passes_seek_filters_and_volume(self) -> None:
        pcm = object()
        transformed = object()

        with (
            patch.object(
                playback, "FFmpegPCMAudio", return_value=pcm
            ) as ffmpeg,
            patch.object(
                playback, "PCMVolumeTransformer", return_value=transformed
            ) as transformer,
        ):
            result = playback.build_audio(
                0.5,
                "https://audio.test/stream",
                io.BytesIO(),
                seek_time=12.5,
                opts=",atempo=1.25",
            )

        self.assertIs(result, transformed)
        self.assertIn("-ss 12.5", ffmpeg.call_args.kwargs["before_options"])
        self.assertIn(",atempo=1.25", ffmpeg.call_args.kwargs["options"])
        transformer.assert_called_once_with(pcm, volume=0.5)

    async def test_join_vc_rejects_dms_and_users_without_voice(self) -> None:
        dm = SimpleNamespace(guild=None, user=object())
        member = SimpleNamespace(voice=None)
        guild_interaction = SimpleNamespace(
            guild=SimpleNamespace(voice_client=None), user=member
        )

        with patch.object(playback, "reply", new=AsyncMock()) as reply_mock:
            self.assertIsNone(await playback.join_vc(as_any(dm)))
            self.assertIsNone(await playback.join_vc(as_any(guild_interaction)))

        self.assertEqual(reply_mock.await_count, 2)

    async def test_join_vc_connects_member_channel_and_returns_voice_client(
        self,
    ) -> None:
        voice_client = object()
        guild = SimpleNamespace(voice_client=None)

        async def connect() -> None:
            guild.voice_client = voice_client

        channel = SimpleNamespace(connect=AsyncMock(side_effect=connect))
        member = SimpleNamespace(voice=SimpleNamespace(channel=channel))
        interaction = SimpleNamespace(guild=guild, user=member)

        result = await playback.join_vc(as_any(interaction))

        self.assertIs(result, voice_client)
        channel.connect.assert_awaited_once_with()


class DiscordHelperTests(unittest.IsolatedAsyncioTestCase):
    async def test_reply_uses_initial_response_or_followup(self) -> None:
        initial = SimpleNamespace(
            is_done=Mock(return_value=False),
            send_message=AsyncMock(return_value="initial"),
        )
        followup = SimpleNamespace(send=AsyncMock(return_value="followup"))
        interaction = SimpleNamespace(response=initial, followup=followup)

        self.assertEqual(
            await helpers.reply(as_any(interaction), "hello"), "initial"
        )
        initial.send_message.assert_awaited_once_with("hello")

        initial.is_done.return_value = True
        self.assertEqual(
            await helpers.reply(as_any(interaction), "again", ephemeral=True),
            "followup",
        )
        followup.send.assert_awaited_once_with("again", ephemeral=True)

    def test_embed_helpers_build_expected_content(self) -> None:
        text_embed = helpers.text_only_embed("Status")
        code_embed = helpers.code_block_embed(["one", "two"], "Commands")

        self.assertEqual(text_embed.author.name, "Status")
        self.assertEqual(code_embed.fields[0].name, "Commands")
        self.assertEqual(code_embed.fields[0].value, "```\none\ntwo\n```")

    def test_gen_bot_thumbnail_uses_packaged_asset(self) -> None:
        file_object = object()
        with patch.object(
            discord, "File", return_value=file_object
        ) as file_class:
            result = helpers.gen_bot_thumbnail()

        self.assertIs(result, file_object)
        path = file_class.call_args.args[0]
        self.assertEqual(path.name, "hatsuneplush.jpg")
        self.assertEqual(
            file_class.call_args.kwargs["filename"], "hatsuneplush.jpg"
        )
