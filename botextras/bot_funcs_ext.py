from __future__ import annotations
import discord
import io
from botextras.constants import FFMPEG_OPTS
from discord import (app_commands, Interaction, WebhookMessage,
    InteractionCallbackResponse, PCMVolumeTransformer, FFmpegPCMAudio)

def owner_command():
    async def predicate(interaction: Interaction)-> bool:
        app = interaction.client.application
        if not app:
            await interaction.client.application_info()
        if interaction.client.application:
            return interaction.user.id == interaction.client.application.owner.id
        return False
    return app_commands.check(predicate)

async def reply(interaction: discord.Interaction, msg: str = "", **kwargs)-> WebhookMessage | InteractionCallbackResponse:
    if interaction.response.is_done():
        return await interaction.followup.send(msg, **kwargs)
    return await interaction.response.send_message(msg, **kwargs)

def build_audio(volume: float, source: str, stderr_buf: io.BytesIO, opts: str = "") -> PCMVolumeTransformer:
    opts = FFMPEG_OPTS["options"] + opts
    pcmaud = FFmpegPCMAudio(source, before_options=FFMPEG_OPTS["before_options"], options=opts, stderr=stderr_buf)
    voltrans_source = PCMVolumeTransformer(pcmaud,volume=volume)
    return voltrans_source

def return_general_embed(txt: str) -> discord.Embed:
    embed = discord.Embed()
    embed.set_author(name=txt)
    return embed
