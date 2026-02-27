import asyncio
import logging
import discord
import random
import io
from discord import Guild, Member, PCMVolumeTransformer, TextChannel, User, VoiceClient, VoiceProtocol, VoiceState, app_commands
from discord.ext import commands
from botextras.audio_handler import get_Audio_Source, get_Song_Info
from botextras.constants import GUILD_OBJECT
from botextras.bot_funcs_ext import reply, build_audio


# TODO add logger
class GuildPlaybackState():
    def __init__(self, guild_id: int):
        self.logger = logging.getLogger(__class__.__name__)
        self.guild_id: int = guild_id
        self.songs_list: list[tuple[str,...]] = []
        self.song_loop: bool = False
        self.source: PCMVolumeTransformer|None = None
        self.vc: VoiceClient|None = None
        self.volume: float = 1.00
        self.text_channel: TextChannel|None = None


    def play_audio(self, source: PCMVolumeTransformer, stderr_buf: io.BytesIO, bot: commands.Bot):
        if self.vc and not self.vc.is_playing():
            self.source = source
            self.vc.play(source, after=lambda error, stderr_buf=stderr_buf:self.playback_callback_func(
                            error,
                            stderr_buf,
                            self.guild_id,
                            bot))

    def playback_callback_func(self, error: Exception | None, stderr_buf: io.BytesIO, g_id: int, bot: commands.Bot) -> None:
        ffmpeg_error = stderr_buf.getvalue().decode("utf-8", errors="ignore")
        if error:
            print(f"Error occured {error}")
        asyncio.run_coroutine_threadsafe(self.helper_play_next(g_id, bot), bot.loop)
        return None

    async def helper_play_next(self, g_id: int, bot: commands.Bot):
        if self.songs_list:
            if not self.song_loop:
                self.songs_list.pop(0)
        if self.songs_list:
            song_title, song_url = self.songs_list[0]
            ffmpeg_source = await get_Audio_Source((song_title,song_url))
            if not ffmpeg_source:
                if self.text_channel:
                    await self.text_channel.send(f"Unable to find audio source for [{song_title}]({song_url}) ! Skipping...")
                self.logger.warning("Bad source for %s, %s", song_title, self.songs_list[0][1])
                self.songs_list.pop(0)
                return await self.helper_play_next(g_id, bot)
            stderr_buf = io.BytesIO()
            source: PCMVolumeTransformer = await asyncio.to_thread(build_audio, self.volume, ffmpeg_source, stderr_buf)
            self.play_audio(source,stderr_buf,bot)
            if self.text_channel:
                await self.text_channel.send(f"Now playing [{song_title}]({song_url}) !")
        if self.text_channel and not self.songs_list:
            await self.text_channel.send("`Queue empty`")
            self.source = None
        return None

    async def voice_cleanup(self, leave_vc: bool = False) -> None:
        self.songs_list = []
        self.song_loop = False
        if self.source:
            self.source.cleanup()
        if self.vc and self.vc.is_playing():
            self.vc.stop()
            if leave_vc:
                await self.vc.disconnect()
        self.source = None
        self.volume = 1.00
        self.vc = None

class reMikuMusicCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.bot: commands.Bot = bot
        self.song_cache: dict[str,str] = {}
        self.last_removed: tuple[str,...] = ()
        self.cache_task = None
        self.guildpback_dict: dict[int,GuildPlaybackState] =  {}

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: Guild) -> None:
        self.logger.info("Bot removed from %s", guild.name)
        self.guildpback_dict.pop(guild.id, None)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: Guild) -> None:
        self.logger.info("Bot joined %s", guild.name)
        self.guildpback_dict.setdefault(guild.id, GuildPlaybackState(guild.id))

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        for g in self.bot.guilds:
            self.guildpback_dict.setdefault(g.id, GuildPlaybackState(g.id))
            self.logger.info("Added %s[%d] to GuildPlaybackState", g.name, g.id)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: Member, before: VoiceState, after: VoiceState) -> None:
        if not self.bot.user or member.id != self.bot.user.id:
            return None
        g_id = member.guild.id
        if not before.channel and after.channel:
            self.logger.info("Bot has joined the voice channel: %s at [%s]", after.channel, member.guild.name)
            if g_id in self.guildpback_dict:
                if isinstance(member.guild.voice_client, VoiceClient):
                    self.guildpback_dict[g_id].vc = member.guild.voice_client
            return None
        if before.channel and not after.channel:
            self.logger.info("Bot has left the voice channel: %s at [%s]", before.channel, member.guild.name)
            if g_id in self.guildpback_dict:
                await self.guildpback_dict[g_id].voice_cleanup()
            return None
        if before.channel != after.channel:
            self.logger.info("Bot has moved from %s to %s at [%s]", before.channel, after.channel, member.guild.name)
        return None


    async def join_vc(self, interaction: discord.Interaction) -> None | VoiceProtocol:
        guild = interaction.guild
        user = interaction.user
        if not guild or isinstance(user, User):
            self.logger.warning("Command used in dm by: %s[%s]", user.name, user.id)
            await reply(interaction, "Erm bot does not work in dms...How did you even add the bot to a dm 😹")
            return None
        if interaction.guild_id not in self.guildpback_dict:
            await reply(interaction, "Bot not worky")
            return None
        state = self.guildpback_dict[interaction.guild_id].vc
        # guild voice client checks if bot is already in voice chat
        # User is for dms, Member is for server use
        if user.voice and user.voice.channel:
            self.logger.debug("%s", self.guildpback_dict[interaction.guild_id].vc)
            if not state:
                await user.voice.channel.connect()
            return guild.voice_client
        else:
            await reply(interaction,"`Join a voice channel first!`", ephemeral=True)
            return None

    @app_commands.command(name="play", description="Enter song name or song url")
    @app_commands.describe(song_name="Currently does not support soundcloud playlists")
    @commands.max_concurrency(1, wait=True)
    @app_commands.guilds(GUILD_OBJECT, discord.Object(id=1476597945540280502))
    async def play(self, interaction: discord.Interaction, song_name: str) -> None:
        g_id = interaction.guild_id
        guild = interaction.guild
        user = interaction.user
        if not g_id or g_id not in self.guildpback_dict or not guild or isinstance(user, User):
            return None
        await interaction.response.defer()
        vc = await self.join_vc(interaction)
        if not isinstance(vc, VoiceClient):
            return None
        gp_state = self.guildpback_dict[g_id]
        song_info = await get_Song_Info(song_name)
        if song_info:
            song_title, song_url = song_info[0]
        else:
            await reply(interaction, "`Invalid link or search!`")
            return None
        if len(song_info[-1]) > 2:
            playlist_name, playlist_link, playlist_count = song_info[-1]
            await reply(interaction, f"Added {playlist_count} songs from [{playlist_name}]({playlist_link}) !")
            gp_state.songs_list.extend(song_info[:-1])
        else:
            await reply(interaction, f"Added [{song_title}]({song_url}) to the queue!")
            gp_state.songs_list.extend(song_info)
        if gp_state.vc and gp_state.vc.is_playing():
            return None
        ffmpeg_source = await get_Audio_Source((song_title,song_url))
        if ffmpeg_source:
            gp_state.text_channel = interaction.channel if isinstance(interaction.channel, TextChannel) else None
            stderr_buf = io.BytesIO()
            source: PCMVolumeTransformer = await asyncio.to_thread(build_audio, gp_state.volume, ffmpeg_source, stderr_buf)
            gp_state.play_audio(source,stderr_buf,self.bot)
            self.logger.info("Playing %s on %s", song_title, guild.name)
            await reply(interaction, f"Now playing [{song_title}]({song_url}) !")
            return None
        else:
            await reply(interaction, "`Something went wrong... try again!`")
        return None


    @app_commands.command(name="queue", description="Gets song queue")
    @app_commands.guilds(GUILD_OBJECT, discord.Object(id=1476597945540280502))
    async def queue(self, interaction: discord.Interaction) -> None:
        g_id = interaction.guild_id
        if not g_id or g_id not in self.guildpback_dict:
            return None
        gp_state = self.guildpback_dict[g_id]
        if not gp_state.songs_list:
            await reply(interaction, "`Queue empty`")
            return None
        queue_str = "```"
        for idx, (song, _) in enumerate(gp_state.songs_list[:11]):
            if song:
                if idx == 0:
                    queue_str += "--> " + song + " <-- Currently playing" + "\n"
                else:
                    queue_str += str(idx) + ". " + song + "\n"
        queue_str += f"Looping current song: {gp_state.song_loop}, Songs in queue: {len(gp_state.songs_list)}"
        queue_str += "```"
        await reply(interaction, queue_str)
        return None

    @app_commands.command(name="skip", description="Skips current song")
    @app_commands.guilds(GUILD_OBJECT, discord.Object(id=1476597945540280502))
    async def skip(self, interaction: discord.Interaction) -> None:
        g_id = interaction.guild_id
        if not g_id or g_id not in self.guildpback_dict:
            await reply(interaction, "Bot not worky")
            return None
        gp_state = self.guildpback_dict[g_id]
        if not gp_state.vc:
            await reply(interaction, "`Not in a voice channel`", ephemeral=True)
            return None
        if not gp_state.songs_list:
            await reply(interaction, "`Queue empty!`")
            return None
        gp_state.song_loop = False
        gp_state.vc.stop()
        await reply(interaction, f"```Skipping {gp_state.songs_list[0][0]}```")
        return None

    @app_commands.command(name="shuffle", description="Shuffles the queue")
    @app_commands.guilds(GUILD_OBJECT, discord.Object(id=1476597945540280502))
    async def shuffle(self, interaction: discord.Interaction) -> None:
        g_id = interaction.guild_id
        if not g_id or g_id not in self.guildpback_dict:
            await reply(interaction, "Bot not worky")
            return None
        gp_state = self.guildpback_dict[g_id]
        if not gp_state.songs_list:
            await reply(interaction, "`Queue empty`")
            return None
        first_song = [gp_state.songs_list[0]]
        exl_first = gp_state.songs_list[1:] if len(gp_state.songs_list) > 1 else []
        random.shuffle(exl_first)
        gp_state.songs_list = first_song + exl_first
        await reply(interaction, "`Queue shuffled`")
        return None

    @app_commands.command(name="loop", description="Loop current song")
    @app_commands.guilds(GUILD_OBJECT, discord.Object(id=1476597945540280502))
    async def loopSong(self, interaction: discord.Interaction) -> None:
        g_id = interaction.guild_id
        if not g_id or g_id not in self.guildpback_dict:
            await reply(interaction, "Bot not worky")
            return None
        gp_state = self.guildpback_dict[g_id]
        if not gp_state.vc:
            await reply(interaction, "`Not in a voice channel!`", ephemeral=True)
            return None
        if not gp_state.song_loop:
            gp_state.song_loop = True
            await reply(interaction, "`Looping current song!`")
            return None
        gp_state.song_loop = False
        await reply(interaction, "`No longer looping current song!`")
        return None

    @app_commands.command(name="remove", description="Remove song from queue")
    @app_commands.describe(index="Must be a valid number to remove")
    @app_commands.guilds(GUILD_OBJECT, discord.Object(id=1476597945540280502))
    async def removeFromQueue(self, interaction: discord.Interaction, index: int) -> None:
        g_id = interaction.guild_id
        if not g_id or g_id not in self.guildpback_dict:
            await reply(interaction, "Bot not worky")
            return None
        gp_state = self.guildpback_dict[g_id]
        try:
            if index == 0:
                raise IndexError
            await reply(interaction,f"```Removing {gp_state.songs_list[index][0]} from queue```")
            gp_state.songs_list.pop(index)
        except IndexError:
            await reply(interaction, "`Not a valid number!`", ephemeral=True)
        return None

    @app_commands.command(name="stop", description="Disconnects bot from voice channel")
    @app_commands.guilds(GUILD_OBJECT, discord.Object(id=1476597945540280502))
    async def stop(self, interaction: discord.Interaction) -> None:
        g_id = interaction.guild_id
        if not g_id or g_id not in self.guildpback_dict:
            await reply(interaction, "Bot not worky")
            return None
        gp_state = self.guildpback_dict[g_id]
        if not gp_state.vc:
            await reply(interaction, "`Not in a voice channel!`")
            return None
        await gp_state.voice_cleanup(leave_vc=True)
        await reply(interaction, "`Stopping playblack...`")
        return None

    @app_commands.command(name="clear", description="Clears music queue")
    @app_commands.guilds(GUILD_OBJECT, discord.Object(id=1476597945540280502))
    async def clear(self, interaction: discord.Interaction) -> None:
        g_id = interaction.guild_id
        if not g_id or g_id not in self.guildpback_dict:
            await reply(interaction, "Bot not worky")
            return None
        gp_state = self.guildpback_dict[g_id]
        if gp_state.vc:
            await gp_state.voice_cleanup()
            await reply(interaction,"`Clearing queue...`")
            return None
        else:
            await reply(interaction,"`Not in a voice channel`", ephemeral=True)
            return None

    @app_commands.command(name="volume", description="Change the volume from 0.00 -> 2.00")
    @app_commands.describe(volume="Select a value between 0-2")
    @app_commands.guilds(GUILD_OBJECT, discord.Object(id=1476597945540280502))
    async def set_volume(self, interaction: discord.Interaction, volume: float) -> None:
        g_id = interaction.guild_id
        if not g_id or g_id not in self.guildpback_dict:
            await reply(interaction, "Bot not worky")
            return None
        gp_state = self.guildpback_dict[g_id]
        if gp_state.source:
            if volume >= 2:
                await reply(interaction, f"`Volume must be less than 2`")
                return None
            gp_state.source.volume = volume
            self.logger.info("Volume set to %f", volume)
            gp_state.volume = volume
            await reply(interaction, f"`Set volume to {volume}!`")
            return None
        await reply(interaction, "`No audio source found!`", ephemeral=True)
        return None

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(reMikuMusicCommands(bot))
