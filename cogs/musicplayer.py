import asyncio
import logging
import discord
import random
import io
from typing import cast, Any
from discord import FFmpegPCMAudio, Guild, InteractionCallbackResponse, Member, PCMVolumeTransformer, TextChannel, VoiceClient, VoiceProtocol, VoiceState, WebhookMessage, app_commands
from discord.ext import commands
from botextras.audio_handler import get_Audio_Source, get_Song_Info
from botextras.constants import GUILD_OBJECT, USER_ID


# TODO add logger
class MikuMusicCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.vc: discord.VoiceClient | None = None
        self.text_channel: discord.TextChannel | None = None
        self.bot: commands.Bot = bot
        # tuple first val is song name, second val is song url
        self.songs_list: list[tuple[str,...]] = []
        self.song_cache: dict[str,str] = {}
        self.song_loop: bool = False
        self.source: PCMVolumeTransformer | None = None
        self.volume: float = 1.00
        self.last_removed: tuple[str,...] = ()
        self.cache_task = None
        self.botguilds:list[Guild] = [n for n in self.bot.guilds]
        self.FFMPEG_OPTS = cast(Any,{
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn",
        })


    @commands.Cog.listener()
    async def on_voice_state_update(self, member: Member, before: VoiceState, after: VoiceState) -> None:
        if not self.bot.user or member.id != self.bot.user.id:
            return None
        if isinstance(member.guild.voice_client, VoiceClient):
            if not before.channel and after.channel:
                    self.logger.info("Bot has joined the voice channel: %s", after.channel)
                    self.vc = member.guild.voice_client
                    return None
        if before.channel and not after.channel:
            self.logger.info("Bot has left the voice channel: %s", before.channel)
            self.vc = None
            self.songs_list = []
            self.song_loop = False
            if self.source:
                self.source.cleanup()
            self.source = None
        return None

    async def cleanup_cache(self, song_url: str)->None:
        #60 minute waiting period
        await asyncio.sleep(6000)
        if song_url in self.song_cache:
            print(f"Removed {song_url} from cache")
            self.song_cache.pop(song_url)
        return None

    async def cache_all(self, song_url: str|None = None, audio_source: str|None = None):
        try:
            if song_url and audio_source:
                self.song_cache[song_url] = audio_source
            if len(self.songs_list) > 1:
                for idx, _ in enumerate(self.songs_list):
                    if not await self.cache_index(idx):
                        continue
                    await asyncio.sleep(30)
            elif len(self.songs_list) == 1:
                await self.cache_index(0)
        except asyncio.CancelledError:
            print("Cache_all cancelled")
            pass

    async def cache_index(self, idx: int = 1)->bool:
        if not self.songs_list:
            return False
        if len(self.songs_list) < idx + 1 and idx != 0:
            return False
        song_title, song_url = self.songs_list[idx]
        if song_title and song_url:
            if song_url not in self.song_cache:
                audio_source = await get_Audio_Source((song_title, song_url))
                if audio_source:
                    self.song_cache[song_url] = audio_source
                    print(f"Caching {song_title} for 60 minutes")
                    asyncio.create_task(self.cleanup_cache(song_url))
                    return True
            else:
                print(f"{song_title} already in cache")
        return False

    async def reply(self, interaction: discord.Interaction, msg: str, **kwargs)-> WebhookMessage | InteractionCallbackResponse:
        if interaction.response.is_done():
            return await interaction.followup.send(msg, **kwargs)
        return await interaction.response.send_message(msg, **kwargs)

    async def join_vc(self, interaction: discord.Interaction) -> None | VoiceProtocol:
        guild = interaction.guild
        user = interaction.user
        assert guild, "Server was not found"
        # guild voice client checks if bot is already in voice chat
        if guild.voice_client:
            return guild.voice_client
        # User is for dms, Member is for server use
        if isinstance(user, discord.Member):
            vc_status = user.voice
            if vc_status and vc_status.channel:
                await vc_status.channel.connect()
                return guild.voice_client
            else:
                await self.reply(interaction,"Join a voice channel first!", ephemeral=True)
                return None
        # returns early if not used in server
        return None

    async def helper_play_next(self, failed: bool = False):
        if self.songs_list:
            if not self.song_loop:
                self.last_removed = self.songs_list[0]
                self.songs_list.pop(0)
            else:
                await self.cache_index(idx=0)
        if self.songs_list:
            song_title, song_url = self.songs_list[0]
            if song_url not in self.song_cache or failed:
                ffmpeg_source = await get_Audio_Source((song_title,song_url))
            else:
                ffmpeg_source = self.song_cache[song_url]
            if not ffmpeg_source:
                if self.text_channel:
                    await self.text_channel.send(f"Unable to find audio source for [{song_title}]({song_url}) ! Skipping...")
                print(f"Bad source for {song_title}, {self.songs_list[0][1]}")
                self.songs_list.pop(0)
                return await self.helper_play_next()
            if ffmpeg_source and self.vc:
                stderr_buf = io.BytesIO()
                pcmaud = FFmpegPCMAudio(ffmpeg_source, **self.FFMPEG_OPTS, stderr=stderr_buf)
                source = PCMVolumeTransformer(pcmaud,volume=self.volume)
                self.source = source
                if not self.vc.is_playing():
                    self.vc.play(
                        source,
                        after=lambda error, song_url=song_url, stderr_buf=stderr_buf: self.playback_callback_func(
                            error,
                            song_url,
                            stderr_buf,
                        ))
                    if self.text_channel:
                        await self.text_channel.send(f"Now playing [{song_title}]({song_url}) !")
        if self.text_channel and not self.songs_list:
            await self.text_channel.send("`Queue empty`")
            self.source = None
        return None

    def playback_callback_func(self, error: Exception | None, song_url: str, stderr_buf: io.BytesIO) -> None:
        failed = False
        ffmpeg_error = stderr_buf.getvalue().decode("utf-8", errors="ignore")
        if "403 Forbidden" in ffmpeg_error:
            if song_url in self.song_cache:
                print(f"Stale audio source for {song_url} removing from cache")
                self.song_cache.pop(song_url)
            failed = True
        if error:
            print(f"Error occured {error}")
        asyncio.run_coroutine_threadsafe(self.helper_play_next(failed=failed), self.bot.loop)
        return None

    @app_commands.command(name="play", description="Enter song name or song url")
    @app_commands.guilds(GUILD_OBJECT, discord.Object(id=1476597945540280502))
    async def play(self, interaction: discord.Interaction, song_name: str) -> None:
        vc: discord.VoiceProtocol | None = await self.join_vc(interaction)
        if not isinstance(vc, VoiceClient):
            return None
        await interaction.response.defer()
        if isinstance(interaction.channel, TextChannel) and not self.text_channel:
            self.text_channel = interaction.channel
        song_info = await get_Song_Info(song_name)
        if not song_info:
            await self.reply(interaction, "`Invalid url or song title.`")
            return None
        song_title, song_url = song_info[0]
        if len(song_info[-1]) > 2:
            playlist_name, playlist_link, playlist_count = song_info[-1]
            await self.reply(interaction, f"Added {playlist_count} songs from [{playlist_name}]({playlist_link}) !")
            self.songs_list.extend(song_info[:-1])
        else:
            await self.reply(interaction, f"Added [{song_title}]({song_url}) to the queue!")
            self.songs_list.extend(song_info)
        if vc.is_playing():
            if self.cache_task:
                self.cache_task.cancel()
                await self.cache_task
            self.cache_task = asyncio.create_task(self.cache_all())
            return None
        if song_url in self.song_cache:
            print(f"Pulling {song_title} from cache")
            ffmpeg_source = self.song_cache[song_url]
        else:
            ffmpeg_source = await get_Audio_Source((song_title,song_url))
        if ffmpeg_source:
            stderr_buf = io.BytesIO()
            pcmaud = FFmpegPCMAudio(ffmpeg_source, **self.FFMPEG_OPTS, stderr=stderr_buf)
            source = PCMVolumeTransformer(pcmaud,volume=self.volume)
            if not vc.is_playing():
                self.source = source
                vc.play(
                    source,
                    after=lambda error, song_url=song_url, stderr_buf=stderr_buf: self.playback_callback_func(
                        error,
                        song_url,
                        stderr_buf,
                    ))
                await self.reply(interaction, f"Now playing [{song_title}]({song_url}) !")
                self.cache_task = asyncio.create_task(self.cache_all(song_url=song_url,audio_source=ffmpeg_source))
                return None
        await self.reply(interaction, "`Something went wrong... try again!`")
        return None

    @app_commands.command(name="stop", description="Disconnects bot from voice channel")
    @app_commands.guilds(GUILD_OBJECT, discord.Object(id=1476597945540280502))
    async def stop(self, interaction: discord.Interaction) -> None:
        if not self.vc:
            await self.reply(interaction, "`Not in a voice channel!`")
            return None
        await self.vc.disconnect()
        self.vc = None
        self.song_loop = False
        self.songs_list = []
        self.source = None
        await self.reply(interaction, "`Stopping playblack...`")
        return None

    @app_commands.command(name="clear", description="Clears music queue")
    @app_commands.guilds(GUILD_OBJECT, discord.Object(id=1476597945540280502))
    async def clear(self, interaction: discord.Interaction) -> None:
        if self.vc:
            self.vc.stop()
            self.song_loop = False
            self.songs_list = []
            self.source = None
            await self.reply(interaction,"`Clearing queue...`")
            return None
        else:
            await self.reply(interaction,"`Not in a voice channel`", ephemeral=True)
            return None

    @app_commands.command(name="queue", description="Gets song queue")
    @app_commands.guilds(GUILD_OBJECT, discord.Object(id=1476597945540280502))
    async def queue(self, interaction: discord.Interaction) -> None:
        if not self.songs_list:
            await self.reply(interaction, "`Queue empty`")
            return None
        queue_str = "```"
        for idx, (song, _) in enumerate(self.songs_list[:11]):
            if song:
                if idx == 0:
                    queue_str += "--> " + song + " <-- Currently playing" + "\n"
                else:
                    queue_str += str(idx) + ". " + song + "\n"
        queue_str += f"Looping current song: {self.song_loop}, Songs in queue: {len(self.songs_list)}"
        queue_str += "```"
        await self.reply(interaction, queue_str)
        return None

    @app_commands.command(name="skip", description="Skips current song")
    @app_commands.guilds(GUILD_OBJECT, discord.Object(id=1476597945540280502))
    async def skip(self, interaction: discord.Interaction) -> None:
        if not self.vc:
            await self.reply(interaction, "`Not in a voice channel`", ephemeral=True)
            return None
        if not self.songs_list:
            await self.reply(interaction, "`Queue empty!`")
            return None
        self.song_loop = False
        self.vc.stop()
        await self.reply(interaction, f"```Skipping {self.songs_list[0][0]}```")
        if self.cache_task:
            self.cache_task.cancel()
            await self.cache_task
        self.cache_task = asyncio.create_task(self.cache_all())
        return None

    @app_commands.command(name="remove", description="Remove song from queue")
    @app_commands.guilds(GUILD_OBJECT, discord.Object(id=1476597945540280502))
    async def removeFromQueue(self, interaction: discord.Interaction, index: int) -> None:
        try:
            if index == 0:
                raise IndexError
            await self.reply(interaction,f"```Removing {self.songs_list[index][0]} from queue```")
            self.songs_list.pop(index)
        except IndexError:
            await self.reply(interaction, "`Not a valid number!`", ephemeral=True)
        return None

    @app_commands.command(name="die", description="Shuts down bot")
    @app_commands.guilds(GUILD_OBJECT, discord.Object(id=1476597945540280502))
    async def die(self, interaction: discord.Interaction) -> None:
        if not USER_ID:
            await self.reply(interaction, "`User ID was never provided`", ephemeral=True)
            return None
        if interaction.user.id == USER_ID:
            if self.vc:
                print("Stopping playable and leaving call")
                self.songs_list = []
                if self.source:
                    self.source.cleanup()
                self.vc.stop()
                await self.vc.disconnect(force=True)
            await self.reply(interaction, "`Shutting down...`")
            await self.bot.close()
            return None
        await self.reply(interaction, "Not allowed", ephemeral=True)
        return None

    @app_commands.command(name="loop", description="Loop current song")
    @app_commands.guilds(GUILD_OBJECT, discord.Object(id=1476597945540280502))
    async def loopSong(self, interaction: discord.Interaction) -> None:
        if not self.vc:
            await interaction.response.send_message("`Not in a voice channel!`", ephemeral=True)
            return None
        if not self.song_loop:
            self.song_loop = True
            await interaction.response.send_message("`Looping current song!`")
            return None
        self.song_loop = False
        await interaction.response.send_message("`No longer looping current song!`")
        return None
    @app_commands.command(name="shuffle", description="Shuffles the queue")
    @app_commands.guilds(GUILD_OBJECT, discord.Object(id=1476597945540280502))
    async def shuffle(self, interaction: discord.Interaction) -> None:
        if not self.songs_list:
            await self.reply(interaction, "`Queue empty`")
            return None
        first_song = [self.songs_list[0]]
        exl_first = self.songs_list[1:] if len(self.songs_list) > 1 else []
        random.shuffle(exl_first)
        self.songs_list = first_song + exl_first
        await self.reply(interaction, "`Queue shuffled`")
        if exl_first and self.cache_task:
            self.cache_task.cancel()
            await self.cache_task
        self.cache_task = asyncio.create_task(self.cache_all())
        return None
    @app_commands.command(name="volume", description="Change the volume from 0.00 -> 2.00")
    @app_commands.guilds(GUILD_OBJECT, discord.Object(id=1476597945540280502))
    async def set_volume(self, interaction: discord.Interaction, volume: float) -> None:
        if self.source:
            if volume > 2:
                await self.reply(interaction, f"`Volume must be less than 2`")
                return None
            self.source.volume = volume
            self.volume = volume
            await self.reply(interaction, f"`Set volume to {volume}!`")
            return None
        await self.reply(interaction, "`No audio source found!`", ephemeral=True)
        return None


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MikuMusicCommands(bot))
