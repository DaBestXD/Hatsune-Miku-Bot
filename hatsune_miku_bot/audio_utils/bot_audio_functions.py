import io
from typing import Literal
from discord import (
    FFmpegPCMAudio,
    PCMVolumeTransformer,
    Interaction,
    VoiceProtocol,
    User,
)
from botextras.constants import FFMPEG_OPTS
from botextras.bot_funcs_ext import reply, text_only_embed


def build_audio(
    volume: float,
    source: str,
    stderr_buf: io.BytesIO,
    seek_time: float = 0,
    opts: str = "",
) -> PCMVolumeTransformer:
    opts = FFMPEG_OPTS["options"] + opts
    before_opts = FFMPEG_OPTS["before_options"] + f" -ss {seek_time}"
    pcmaud = FFmpegPCMAudio(
        source, before_options=before_opts, options=opts, stderr=stderr_buf
    )
    return PCMVolumeTransformer(pcmaud, volume=volume)


async def join_vc(interaction: Interaction, join: bool = True) -> None | VoiceProtocol:
    guild = interaction.guild
    user = interaction.user
    if not guild or isinstance(user, User):
        await reply(
            interaction,
            "Erm bot does not work in dms...How did you even add the bot to a dm 😹",
        )
        return None
    # guild voice client checks if bot is already in voice chat
    # User is for dms, Member is for server use
    if user.voice and user.voice.channel:
        if not guild.voice_client and join:
            await user.voice.channel.connect()
        return guild.voice_client
    else:
        await reply(
            interaction,
            embed=text_only_embed("Join a voice channel first!"),
            ephemeral=True,
        )
        return None


async def mod_song(
    mod_type: Literal["pitch", "speed", "bass", "off"], effect_strength: float = 0
) -> str:
    song_mods = ""
    if mod_type == "pitch":
        song_mods = f",aresample=48000,asetrate=48000*{effect_strength},aresample=48000"
    elif mod_type == "speed":
        song_mods = f",atempo={effect_strength}"
    elif mod_type == "bass":
        song_mods = f",bass=g={effect_strength}"
    elif mod_type == "off":
        song_mods = ""
    return song_mods
