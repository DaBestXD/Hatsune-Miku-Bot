import io
from discord import FFmpegPCMAudio, PCMVolumeTransformer, Interaction, VoiceProtocol, User
from botextras.constants import FFMPEG_OPTS
from botextras.bot_funcs_ext import reply, txt_only_embed

def build_audio(volume: float, source: str, stderr_buf: io.BytesIO, seek_time: float = 0,opts: str = "") -> PCMVolumeTransformer:
    opts = FFMPEG_OPTS["options"] + opts
    before_opts = FFMPEG_OPTS["before_options"] + f" -ss {seek_time}"
    pcmaud = FFmpegPCMAudio(source, before_options=before_opts, options=opts, stderr=stderr_buf)
    return PCMVolumeTransformer(pcmaud,volume=volume)

async def join_vc(interaction: Interaction) -> None|VoiceProtocol:
    guild = interaction.guild
    user = interaction.user
    if not guild or isinstance(user, User):
        await reply(interaction, "Erm bot does not work in dms...How did you even add the bot to a dm 😹")
        return None
    # guild voice client checks if bot is already in voice chat
    # User is for dms, Member is for server use
    if user.voice and user.voice.channel:
        if not guild.voice_client:
            await user.voice.channel.connect()
        return guild.voice_client
    else:
        await reply(interaction,embed=txt_only_embed("Join a voice channel first!"), ephemeral=True)
        return None

