import discord
import io
from botextras.constants import FFMPEG_OPTS
from discord import app_commands, Interaction, WebhookMessage, InteractionCallbackResponse, PCMVolumeTransformer, FFmpegPCMAudio

def owner_command():
    async def predicate(interaction: Interaction)-> bool:
        app = interaction.client.application
        if not app:
            await interaction.client.application_info()
        if interaction.client.application:
            return interaction.user.id == interaction.client.application.owner.id
        return False
    return app_commands.check(predicate)

async def reply(interaction: discord.Interaction, msg: str, **kwargs)-> WebhookMessage | InteractionCallbackResponse:
    if interaction.response.is_done():
        return await interaction.followup.send(msg, **kwargs)
    return await interaction.response.send_message(msg, **kwargs)

def build_audio(volume: float, source: str, stderr_buf: io.BytesIO) -> PCMVolumeTransformer:
    pcmaud = FFmpegPCMAudio(source, **FFMPEG_OPTS, stderr=stderr_buf)
    voltrans_source = PCMVolumeTransformer(pcmaud,volume=volume)
    return voltrans_source
