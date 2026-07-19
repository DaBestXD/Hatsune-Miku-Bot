import io
from typing import TypedDict

from discord import (
    FFmpegPCMAudio,
    Interaction,
    PCMVolumeTransformer,
    User,
    VoiceProtocol,
)

from hatsune_miku_bot.utils.discord_helpers import reply, text_only_embed


class FFMpegOpts(TypedDict):
    before_options: str
    options: str


FFMPEG_OPTS: FFMpegOpts = {
    "before_options": "-nostdin -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",  # noqa: E501
    "options": "-vn -af loudnorm=I=-12:TP=-1.0:LRA=7",
}


def build_audio(
    volume: float,
    source: str,
    stderr_buf: io.BytesIO,
    seek_time: float = 0,
    opts: str = "",
) -> PCMVolumeTransformer[FFmpegPCMAudio]:
    opts = FFMPEG_OPTS["options"] + opts
    before_opts = FFMPEG_OPTS["before_options"] + f" -ss {seek_time}"
    pcmaud = FFmpegPCMAudio(
        source, before_options=before_opts, options=opts, stderr=stderr_buf
    )
    return PCMVolumeTransformer(pcmaud, volume=volume)


async def join_vc(
    interaction: Interaction, join: bool = True
) -> None | VoiceProtocol:
    guild = interaction.guild
    user = interaction.user
    if not guild or isinstance(user, User):
        await reply(
            interaction,
            "Erm bot does not work in dms...How did you even add the bot to a dm 😹",  # noqa: E501
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
