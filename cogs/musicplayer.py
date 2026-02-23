import asyncio
import discord
import random
import io
from typing import cast
from discord import FFmpegPCMAudio, InteractionCallbackResponse, PCMVolumeTransformer, VoiceClient, VoiceProtocol, WebhookMessage, app_commands
from discord.ext import commands
from botextras.audio_handler import get_Audio_Source, get_Song_Info
from botextras.constants import GUILD_OBJECT, USER_ID


# TODO add logger
class MikuMusicCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.vc: discord.VoiceClient | None = None
        self.text_channel: discord.TextChannel | None = None
        self.bot: commands.Bot = bot
        # tuple first val is song name, second val is song url
        self.songs_list: list[tuple[str|None,... ]] = []
        self.song_cache: dict[str,str] = {}
        self.playback_status: bool = False
        self.song_loop: bool = False
        self.source: PCMVolumeTransformer | None = None
        self.volume: float = 1.00
        self.last_removed: tuple[str|None,...]= ()
        self.stderr_buf = None
        self.FFMPEG_OPTS: dict[str, str] = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn",
        }

    async def cleanup_cache(self, song_url: str)->None:
        print(f"Removing {song_url} in 10 minutes")
        await asyncio.sleep(600)
        if song_url in self.song_cache:
            print(f"Removed {song_url} from cache")
            self.song_cache.pop(song_url)
        return None

    async def cache_index(self, idx: int = 1)->None:
        if len(self.songs_list) < idx + 1:
            print(f"{self.songs_list} less than {idx}")
            return None
        song_title, song_url = self.songs_list[idx]
        if song_title and song_url:
            if song_url not in self.song_cache:
                audio_source = await get_Audio_Source((song_title, song_url))
                if audio_source:
                    self.song_cache[song_url] = audio_source
                    print(f"Caching {song_title}")
                    asyncio.create_task(self.cleanup_cache(song_url))
            else:
                print(f"{song_title} already in cache")
        return None

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

    async def helper_play_next(self, failed :bool=False):
        last_song = True
        if self.songs_list and not failed:
            if not self.song_loop:
                self.last_removed = self.songs_list[0]
                self.songs_list.pop(0)
        if failed:
            self.songs_list.insert(0, self.last_removed)
        if self.songs_list:
            await self.cache_index()
            last_song = False
            song_title, song_url = self.songs_list[0]
            self.stderr_buf = io.BytesIO()
            if song_url not in self.song_cache:
                ffmpeg_source = await get_Audio_Source((song_title,song_url))
            else:
                ffmpeg_source = self.song_cache[song_url]
                self.song_cache.pop(song_url)
            if ffmpeg_source and self.vc:
                source = PCMVolumeTransformer(FFmpegPCMAudio(
                    ffmpeg_source,
                    before_options=self.FFMPEG_OPTS["before_options"],
                    options=self.FFMPEG_OPTS["options"],
                    stderr=self.stderr_buf
                ),volume=self.volume)
                self.source = source
                self.vc.play(source, after=self.playback_callback_func)
                if self.text_channel:
                    await self.text_channel.send(f"Now playing [{song_title}]({song_url}) !")
            else:
                # Unable to find ffmpeg source move to next song
                return self.helper_play_next()
        if self.text_channel and last_song:
            await self.text_channel.send("`Queue empty`")
            self.playback_status = False
            self.source = None
        return None

    def playback_callback_func(self, error):
        failed = False
        if self.stderr_buf:
            ffmpeg_error = self.stderr_buf.getvalue().decode("utf-8",errors="ignore")
            if "403 Forbidden" in ffmpeg_error:
                failed = True
        if error:
            print(f"Error occured {error}")
            return None
        asyncio.run_coroutine_threadsafe(self.helper_play_next(failed), self.bot.loop)
        return None

    @app_commands.command(name="play", description="Enter song name or song url")
    @app_commands.guilds(GUILD_OBJECT)
    async def play(self, interaction: discord.Interaction, song_name: str) -> None:
        vc: discord.VoiceProtocol | None = await self.join_vc(interaction)
        if not vc:
            return None
        await interaction.response.defer()
        # VoiceProtocol and VoiceClient effectively the same (maybe true?)
        # VoiceClient has auto completion for text editors, pyright gets mad otherwise
        vc = cast(VoiceClient, vc)
        # set text channel so playnext callback function able to send to correct channel
        self.text_channel = (cast(discord.TextChannel, interaction.channel) if not self.text_channel else self.text_channel)
        song_info = await get_Song_Info(song_name)
        if not song_info:
            await interaction.followup.send("`Invalid url or song title.`")
            return None
        if len(song_info) > 1:
            *songs, playlist_info = song_info
            playlist_name, playlist_link, playlist_count = playlist_info
            song_title, song_url = songs[0]
            self.songs_list.extend(songs)
            await self.reply(interaction, f"Added {playlist_count} songs from [{playlist_name}]({playlist_link}) !")
            if vc.is_playing():
                return None
            ffmpeg_source = await get_Audio_Source((song_title,song_url))
        else:
            song_title, song_url = song_info[0]
            self.songs_list.extend(song_info)
            await self.reply(interaction, f"Added [{song_title}]({song_url}) to the queue!")
            if vc.is_playing():
                return None
            ffmpeg_source = await get_Audio_Source((song_title,song_url))
        if ffmpeg_source:
            source = PCMVolumeTransformer(FFmpegPCMAudio(
                ffmpeg_source,
                before_options=self.FFMPEG_OPTS["before_options"],
                options=self.FFMPEG_OPTS["options"],
            ),volume=self.volume)
            self.source = source
            self.vc = vc
            vc.play(source, after=self.playback_callback_func)
            await self.reply(interaction, f"Now playing [{song_title}]({song_url}) !")
            await self.cache_index()
            return None
        else:
            await self.reply(interaction, "`Something went wrong... try again!`")
            return None

    @app_commands.command(name="stop", description="Disconnects bot from voice channel")
    @app_commands.guilds(GUILD_OBJECT)
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
    @app_commands.guilds(GUILD_OBJECT)
    async def clear(self, interaction: discord.Interaction) -> None:
        if self.vc:
            self.vc.stop()
            self.vc = None
            self.song_loop = False
            self.songs_list = []
            self.source = None
            await self.reply(interaction,"`Clearing queue...`")
            return None
        else:
            await self.reply(interaction,"`Not in a voice channel`", ephemeral=True)
            return None

    @app_commands.command(name="queue", description="Gets song queue")
    @app_commands.guilds(GUILD_OBJECT)
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
        queue_str += "```"
        await self.reply(interaction, queue_str)
        return None

    @app_commands.command(name="skip", description="Skips current song")
    @app_commands.guilds(GUILD_OBJECT)
    async def skip(self, interaction: discord.Interaction) -> None:
        if not self.vc:
            await self.reply(interaction, "`Not in a voice channel`", ephemeral=True)
            return None
        self.song_loop = False
        self.vc.stop()
        await self.reply(interaction, f"```Skipping {self.songs_list[0][0]}```")
        return None

    @app_commands.command(name="remove", description="Remove song from queue")
    @app_commands.guilds(GUILD_OBJECT)
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
    @app_commands.guilds(GUILD_OBJECT)
    async def die(self, interaction: discord.Interaction) -> None:
        if not USER_ID:
            await self.reply(interaction, "`User ID was never provided`", ephemeral=True)
            return None
        if interaction.user.id == USER_ID:
            await self.reply(interaction, "`Shutting down...`")
            await self.bot.close()
            return None
        await self.reply(interaction, "Not allowed", ephemeral=True)
        return None

    @app_commands.command(name="loop", description="Loop current song")
    @app_commands.guilds(GUILD_OBJECT)
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
    @app_commands.guilds(GUILD_OBJECT)
    async def shuffle(self, interaction: discord.Interaction) -> None:
        if not self.songs_list:
            await self.reply(interaction, "`Queue empty`")
            return None
        first_song = [self.songs_list[0]]
        exl_first = self.songs_list[1:] if len(self.songs_list) > 1 else []
        random.shuffle(exl_first)
        self.songs_list = first_song + exl_first
        await self.reply(interaction, "`Queue shuffled`")
        if exl_first:
            await self.cache_index()
        return None
    @app_commands.command(name="volume", description="Change the volume from 0.00 -> 2.00")
    @app_commands.guilds(GUILD_OBJECT)
    async def set_volume(self, interaction: discord.Interaction, volume: float) -> None:
        if self.source:
            if volume > 2:
                await self.reply(interaction, f"`Volume must be less than 2`")
                return None
            self.source.volume = volume
            self.volume = volume
            await interaction.response.send_message(f"`Set volume to {volume}!`")
            return None
        await self.reply(interaction, "`No audio source found!`", ephemeral=True)
        return None


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MikuMusicCommands(bot))
