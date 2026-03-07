from __future__ import annotations
import asyncio
import logging
from typing import Literal
import discord
import random
import io
import time
from discord import (Guild, Member, PCMVolumeTransformer, TextChannel, User,
    VoiceClient, VoiceProtocol, VoiceState, app_commands)
from discord.ext import commands
from botextras.audioClass import Song, Playlist
from botextras.audio_handler import get_Audio_Source, get_Song_Info
from botextras.bot_funcs_ext import reply, build_audio, txt_only_embed
from botextras.constants import CACHE_TIMER, GUILD_OBJECT

class GuildPlaybackState():
    def __init__(self, guild_id: int):
        self.logger = logging.getLogger(__class__.__name__)
        self.guild_id: int = guild_id
        self.song_cache: dict[str,str] = {}
        self.songs_list: list[Song]= []
        self.song_loop: bool = False
        self.source: PCMVolumeTransformer|None = None
        self.vc: VoiceClient|None = None
        self.volume: float = 1.00
        self.text_channel: TextChannel|None = None
        self.cache_task: asyncio.Task|None = None
        self.start_time: float|None = None
        self.seek_time: float|None = None
        self.song_mods: str = ""
        self.mod_mid_song: bool = False
        self.nightcore: bool = False

    def start_timer(self):
        self.start_time = time.monotonic() if not self.start_time else self.start_time
        self.mod_mid_song = False
    def end_timer(self):
        self.start_time = None

    async def cleanup_cache(self, song_url: str) -> None:
        # 15 minutes wait time
        await asyncio.sleep(CACHE_TIMER)
        if song_url in self.song_cache:
            self.logger.info("Removed %s from cache", song_url)
            self.song_cache.pop(song_url)
        return None

    async def cache_songs(self, song_url: str|None = None, audio_source: str|None = None, cache_limit: int = 10) -> None:
        try:
            if song_url and audio_source:
                self.song_cache[song_url] = audio_source
            if len(self.songs_list) > 1:
                for idx, _ in enumerate(self.songs_list[:cache_limit]):
                    if not await self.cache_index(idx):
                        continue
                    await asyncio.sleep(30)
            elif len(self.songs_list) == 1:
                await self.cache_index(0)
            return None
        except asyncio.CancelledError:
            return None

    async def cache_index(self, idx: int = 1) -> bool:
        if not self.songs_list:
            return False
        if len(self.songs_list) < idx + 1 and idx != 0:
            return False
        song = self.songs_list[idx]
        if song.webpage_url not in self.song_cache:
            audio_source = await get_Audio_Source((song.title, song.webpage_url))
            if audio_source:
                self.song_cache[song.webpage_url] = audio_source
                self.logger.info("Caching %s for 60 minutes", song.title)
                asyncio.create_task(self.cleanup_cache(song.webpage_url))
                return True
            else:
                self.logger.info("%s already in cache", song.title)
        return False


    def play_audio(self, source: PCMVolumeTransformer, stderr_buf: io.BytesIO, bot: commands.Bot, song_url: str):
        if self.vc and not self.vc.is_playing():
            self.source = source
            self.vc.play(source, after=lambda error, stderr_buf=stderr_buf:self.playback_callback_func(
                            error,
                            stderr_buf,
                            self.guild_id,
                            bot,
                            song_url))
            self.start_timer()

    def playback_callback_func(self, error: Exception | None, stderr_buf: io.BytesIO, g_id: int, bot: commands.Bot, song_url: str) -> None:
        if not self.mod_mid_song:
            self.end_timer()
        ffmpeg_error = stderr_buf.getvalue().decode("utf-8", errors="ignore")
        failed = False
        if "403 Forbidden" in ffmpeg_error and song_url in self.song_cache:
            self.logger.info("Stale audio source for %s removing from cache", song_url)
            self.song_cache.pop(song_url)
            failed = True
        if error:
            self.logger.error("Error occured %s", error)
        asyncio.run_coroutine_threadsafe(self.helper_play_next(g_id, bot, failed), bot.loop)
        return None

    async def helper_play_next(self, g_id: int, bot: commands.Bot, failed: bool = False):
        if self.songs_list:
            if not self.song_loop:
                self.songs_list.pop(0)
        if self.songs_list:
            song = self.songs_list[0]
            if song.webpage_url in self.song_cache and not failed:
                ffmpeg_source = self.song_cache[song.webpage_url]
            else:
                ffmpeg_source = await get_Audio_Source((song.title,song.webpage_url))
            if not ffmpeg_source:
                if self.text_channel:
                    await self.text_channel.send(embed=song.return_err_embed())
                self.logger.error("Bad source for %s, %s", song.title, song.webpage_url)
                self.songs_list.pop(0)
                return await self.helper_play_next(g_id, bot)
            stderr_buf = io.BytesIO()
            music_start = self.seek_time if self.seek_time else 0
            source: PCMVolumeTransformer = await asyncio.to_thread(build_audio, self.volume, ffmpeg_source, stderr_buf, seek_time=music_start,opts=self.song_mods)
            self.play_audio(source,stderr_buf,bot,song.webpage_url)
            if self.text_channel:
                next_song = self.songs_list[1] if len(self.songs_list) >= 2 else None
                if not self.mod_mid_song:
                    await self.text_channel.send(embed=song.return_embed(next_song))
        if self.text_channel and not self.songs_list:
            await self.text_channel.send(embed=txt_only_embed("Queue empty"))
            self.source = None
        if self.song_loop:
            await self.override_task()
        return None

    async def voice_cleanup(self, leave_vc: bool = False) -> None:
        self.songs_list = []
        self.song_loop = False
        if self.source:
            self.source.cleanup()
        if self.vc:
            if self.vc.is_playing():
                self.vc.stop()
            if leave_vc:
                await self.vc.disconnect()
        self.source = None
        self.volume = 1.00
        self.vc = None

    async def override_task(self) -> None:
        if self.cache_task:
            self.cache_task.cancel()
            await self.cache_task
        self.cache_task = asyncio.create_task(self.cache_songs())
        return None

class MikuMusicCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.bot: commands.Bot = bot
        self.song_cache: dict[str,str] = {}
        self.cache_task = None
        self.guildpback_dict: dict[int,GuildPlaybackState] =  {}
        self.synced: bool = False

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: Guild) -> None:
        self.logger.info("Removed %s[%d] from GuildPlaybackState", guild.name, guild.id)
        self.guildpback_dict.pop(guild.id, None)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: Guild) -> None:
        self.logger.info("Added %s[%d] to GuildPlaybackState", guild.name, guild.id)
        self.guildpback_dict.setdefault(guild.id, GuildPlaybackState(guild.id))

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if not self.synced:
            for g in self.bot.guilds:
                self.guildpback_dict.setdefault(g.id, GuildPlaybackState(g.id))
                self.logger.info("Added %s[%d] to GuildPlaybackState", g.name, g.id)
            self.synced = True
        else:
            self.logger.info("GuildPlaybackState dict already initialized")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: Member, before: VoiceState, after: VoiceState) -> None:
        if not self.bot.user or member.id != self.bot.user.id:
            return None
        g_id = member.guild.id
        if not g_id in self.guildpback_dict:
            return None
        gp_state = self.guildpback_dict[g_id]
        if not before.channel and after.channel:
            self.logger.info("Bot has joined the voice channel: %s at [%s]", after.channel, member.guild.name)
            if isinstance(member.guild.voice_client, VoiceClient):
                gp_state.vc = member.guild.voice_client
            return None
        if before.channel and not after.channel:
            self.logger.info("Bot has left the voice channel: %s at [%s]", before.channel, member.guild.name)
            if g_id in self.guildpback_dict:
                gp_state.vc = None
            return None
        if before.channel != after.channel:
            self.logger.info("Bot has moved from %s to %s at [%s]", before.channel, after.channel, member.guild.name)
        return None


    async def join_vc(self, interaction: discord.Interaction) -> None | VoiceProtocol:
        guild = interaction.guild
        user = interaction.user
        if not guild or isinstance(user, User):
            self.logger.warning("Command used in dm by: %s[%d]", user.name, user.id)
            await reply(interaction, "Erm bot does not work in dms...How did you even add the bot to a dm 😹")
            return None
        if interaction.guild_id not in self.guildpback_dict:
            await reply(interaction, "Bot not worky")
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

    @app_commands.command(name="play", description="Enter song name or song url")
    @app_commands.describe(song_name="Currently does not support soundcloud playlists")
    @commands.max_concurrency(1, wait=True)
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
        if not song_info:
            await reply(interaction, embed=txt_only_embed("Invalid link or song"))
            return None
        next_song = gp_state.songs_list[1] if len(gp_state.songs_list) >= 2 else None
        if isinstance(song_info, Playlist):
            await reply(interaction, embed=song_info.return_embed())
            gp_state.songs_list.extend(song_info.songs)
            song_info = song_info.songs[0]
        else:
            await reply(interaction, embed=song_info.return_embed(queued=True,next_song=next_song))
            gp_state.songs_list.append(song_info)
        if gp_state.vc and gp_state.vc.is_playing():
            await gp_state.override_task()
            return None
        if song_info.webpage_url in gp_state.song_cache:
            ffmpeg_source = gp_state.song_cache[song_info.webpage_url]
        else:
            ffmpeg_source = await get_Audio_Source((song_info.title,song_info.webpage_url))
        if ffmpeg_source:
            gp_state.text_channel = interaction.channel if isinstance(interaction.channel, TextChannel) else None
            stderr_buf = io.BytesIO()
            source: PCMVolumeTransformer = await asyncio.to_thread(build_audio, gp_state.volume, ffmpeg_source, stderr_buf, opts=gp_state.song_mods)
            gp_state.play_audio(source,stderr_buf,self.bot,song_info.webpage_url)
            self.logger.info("Playing %s on %s[%d]", song_info.title, guild.name, guild.id)
            await reply(interaction, embed=song_info.return_embed(next_song))
            gp_state.cache_task = asyncio.create_task(gp_state.cache_songs(song_info.webpage_url,ffmpeg_source))
            return None
        else:
            await reply(interaction, embed=txt_only_embed("Something went wrong... try again!"))
        return None


    @app_commands.command(name="queue", description="Gets song queue")
    async def queue(self, interaction: discord.Interaction) -> None:
        g_id = interaction.guild_id
        if not g_id or g_id not in self.guildpback_dict:
            return None
        gp_state = self.guildpback_dict[g_id]
        if not gp_state.songs_list:
            await reply(interaction, embed=txt_only_embed("Queue empty"))
            return None
        queue_playlist = Playlist(gp_state.songs_list,playlist_title="Current Queue")
        embed,file = queue_playlist.return_queue_embed()
        await reply(interaction, embed=embed, file=file)
        return None

    @app_commands.command(name="skip", description="Skips current song")
    async def skip(self, interaction: discord.Interaction) -> None:
        g_id = interaction.guild_id
        if not g_id or g_id not in self.guildpback_dict:
            await reply(interaction, "Bot not worky")
            return None
        gp_state = self.guildpback_dict[g_id]
        if not gp_state.vc:
            await reply(interaction, embed=txt_only_embed("Not in a voice channel"), ephemeral=True)
            return None
        if not gp_state.songs_list:
            await reply(interaction, embed=txt_only_embed("Queue empty!"))
            return None
        gp_state.song_loop = False
        gp_state.vc.stop()
        next_song = gp_state.songs_list[1] if len(gp_state.songs_list) >= 2 else None
        await reply(interaction, embed=gp_state.songs_list[0].return_skip_embed(next_song))
        await gp_state.override_task()
        return None

    @app_commands.command(name="shuffle", description="Shuffles the queue")
    async def shuffle(self, interaction: discord.Interaction) -> None:
        g_id = interaction.guild_id
        if not g_id or g_id not in self.guildpback_dict:
            await reply(interaction, "Bot not worky")
            return None
        gp_state = self.guildpback_dict[g_id]
        if not gp_state.songs_list:
            await reply(interaction, embed=txt_only_embed("Queue empty"))
            return None
        first_song = [gp_state.songs_list[0]]
        exl_first = gp_state.songs_list[1:] if len(gp_state.songs_list) > 1 else []
        random.shuffle(exl_first)
        gp_state.songs_list = first_song + exl_first
        await reply(interaction, embed=txt_only_embed("Queue shuffled"))
        if exl_first:
            await gp_state.override_task()
        return None

    @app_commands.command(name="loop", description="Loop current song")
    async def loopSong(self, interaction: discord.Interaction) -> None:
        g_id = interaction.guild_id
        if not g_id or g_id not in self.guildpback_dict:
            await reply(interaction, "Bot not worky")
            return None
        gp_state = self.guildpback_dict[g_id]
        if not gp_state.vc:
            await reply(interaction, embed=txt_only_embed("Not in a voice channel!"), ephemeral=True)
            return None
        if not gp_state.song_loop:
            gp_state.song_loop = True
            await reply(interaction, embed=txt_only_embed("Looping current song!"))
            return None
        gp_state.song_loop = False
        await reply(interaction, embed=txt_only_embed("No longer looping current song!"))
        return None

    @app_commands.command(name="remove", description="Remove song from queue")
    @app_commands.describe(index="Must be a valid number to remove")
    async def removeFromQueue(self, interaction: discord.Interaction, index: int) -> None:
        g_id = interaction.guild_id
        if not g_id or g_id not in self.guildpback_dict:
            await reply(interaction, "Bot not worky")
            return None
        gp_state = self.guildpback_dict[g_id]
        try:
            if index == 0 or index < 0:
                raise IndexError
            await reply(interaction,embed=txt_only_embed(f"Removing {gp_state.songs_list[index].title} from queue"))
            gp_state.songs_list.pop(index)
        except IndexError:
            await reply(interaction, embed=txt_only_embed("Not a valid number!"), ephemeral=True)
        return None

    @app_commands.command(name="stop", description="Disconnects bot from voice channel")
    async def stop(self, interaction: discord.Interaction) -> None:
        g_id = interaction.guild_id
        if not g_id or g_id not in self.guildpback_dict:
            await reply(interaction, "Bot not worky")
            return None
        gp_state = self.guildpback_dict[g_id]
        if not gp_state.vc:
            await reply(interaction, embed=txt_only_embed("Not in a voice channel!"))
            return None
        await gp_state.voice_cleanup(leave_vc=True)
        await reply(interaction, embed=txt_only_embed("Stopping playblack..."))
        return None

    @app_commands.command(name="clear", description="Clears music queue")
    async def clear(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        g_id = interaction.guild_id
        if not guild or not g_id or g_id not in self.guildpback_dict:
            return None
        gp_state = self.guildpback_dict[g_id]
        if guild.voice_client and gp_state.vc:
            gp_state.vc.stop()
            gp_state.songs_list = []
            await reply(interaction,embed=txt_only_embed("Clearing queue..."))
            return None
        else:
            await reply(interaction,embed=txt_only_embed("Not in a voice channel"), ephemeral=True)
            return None

    @app_commands.command(name="volume", description="Change the volume from 0.00 -> 2.00")
    @app_commands.describe(volume="Select a value between 0-2")
    async def set_volume(self, interaction: discord.Interaction, volume: app_commands.Range[float,0.0,2.0]) -> None:
        g_id = interaction.guild_id
        if not g_id or g_id not in self.guildpback_dict:
            await reply(interaction, "Bot not worky")
            return None
        gp_state = self.guildpback_dict[g_id]
        if gp_state.source:
            gp_state.source.volume = volume
            gp_state.volume = volume
        await reply(interaction, embed=txt_only_embed(f"Set volume to: {gp_state.volume}"))
        return None
    @app_commands.command(name="night-core", description="Toggle night-core")
    @app_commands.guilds(GUILD_OBJECT, discord.Object(id=1476597945540280502))
    async def night_core(self, interaction: discord.Interaction):
        await interaction.response.defer()
        g_id = interaction.guild_id
        if not g_id or g_id not in self.guildpback_dict:
            return None
        gp_state = self.guildpback_dict[g_id]
        if not gp_state.nightcore:
            await self.mod_song(interaction,"pitch" ,1.25)
            await reply(interaction, embed=txt_only_embed("Nightcore on!🙀"))
        else:
            await self.mod_song(interaction, "pitch", 1)
            await reply(interaction, embed=txt_only_embed("Nightcore off!😿"))
        gp_state.nightcore = not gp_state.nightcore
        return None

    async def mod_song(self, interaction: discord.Interaction, mod_type: Literal["pitch","speed"], effect_strength: app_commands.Range[float,0.0,2.0]) -> None:
        g_id = interaction.guild_id
        if not g_id or g_id not in self.guildpback_dict:
            return None
        gp_state = self.guildpback_dict[g_id]
        if gp_state.vc and gp_state.vc.is_playing():
            gp_state.mod_mid_song = True
            gp_state.songs_list.insert(1,gp_state.songs_list[0])
            if gp_state.start_time:
                gp_state.seek_time = time.monotonic() - gp_state.start_time
            if mod_type == "pitch":
                gp_state.song_mods = f",aresample=48000,asetrate=48000*{effect_strength},aresample=48000"
            else:
                gp_state.song_mods = f",atempo={effect_strength}"
            gp_state.mod_mid_song = False
            gp_state.seek_time = None
            gp_state.vc.stop()
        return None

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MikuMusicCommands(bot))
