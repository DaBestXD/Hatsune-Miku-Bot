from __future__ import annotations
import asyncio
import logging
import discord
import random
import io
import time
from typing import Literal
from discord import (Guild, Interaction, Member, PCMVolumeTransformer, TextChannel,
    VoiceClient,VoiceState,app_commands)
from discord.ext import commands
from audio_utils.audio_class import Playlist, Song
from audio_utils.audio_handler import get_Audio_Source, get_Song_Info
from audio_utils.guild_playback_state import GuildPlaybackState
from audio_utils.music_queue_classes import QueueEmbed, QueueView
from audio_utils.bot_audio_functions import build_audio, join_vc
from botextras.bot_funcs_ext import reply, txt_only_embed,gen_bot_thumbnail


class MikuMusicCommands(commands.Cog):
    """
    Stores all the music slash commands
    Cogname: musicplayer
    """
    def __init__(self, bot: commands.Bot) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.bot: commands.Bot = bot
        self.song_cache: dict[str,str] = {}
        self.cache_task = None
        self.guildpback_dict: dict[int,GuildPlaybackState] =  {}
        self.synced: bool = False

    def return_gp_state(self, interaction: discord.Interaction) -> GuildPlaybackState|None:
        if g_id:= interaction.guild_id:
            return self.guildpback_dict.get(g_id)
        return None

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: Guild) -> None:
        self.logger.info("Removed %s[%d] from GuildPlaybackState", guild.name, guild.id)
        self.guildpback_dict.pop(guild.id, None)
        return None

    @commands.Cog.listener()
    async def on_guild_join(self, guild: Guild) -> None:
        self.logger.info("Added %s[%d] to GuildPlaybackState", guild.name, guild.id)
        self.guildpback_dict.setdefault(guild.id, GuildPlaybackState(guild.id))
        return None

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if not self.synced:
            for g in self.bot.guilds:
                self.guildpback_dict.setdefault(g.id, GuildPlaybackState(g.id))
                self.logger.info("Added %s[%d] to GuildPlaybackState", g.name, g.id)
            self.synced = True
        else:
            self.logger.info("GuildPlaybackState dict already initialized")
        return None

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: Member, before: VoiceState, after: VoiceState) -> None:
        if not self.bot.user or member.id != self.bot.user.id:
            return None
        if not (gp_state := self.guildpback_dict.get(member.guild.id)):
            return None
        if not before.channel and after.channel:
            self.logger.debug("Bot has joined the voice channel: %s at [%s]", after.channel, member.guild.name)
            if isinstance(member.guild.voice_client, VoiceClient):
                gp_state.vc = member.guild.voice_client
            return None
        if before.channel and not after.channel:
            self.logger.debug("Bot has left the voice channel: %s at [%s]", before.channel, member.guild.name)
            gp_state.vc = None
            return None
        if before.channel != after.channel:
            self.logger.debug("Bot has moved from %s to %s at [%s]", before.channel, after.channel, member.guild.name)
        return None

    async def _start_playback(self, interaction: Interaction, song: Song, gp_state: GuildPlaybackState):
        if song.webpage_url in gp_state.song_cache:
            ffmpeg_source = gp_state.song_cache[song.webpage_url]
        else:
            ffmpeg_source = await get_Audio_Source((song.title,song.webpage_url))
        if ffmpeg_source:
            stderr_buf = io.BytesIO()
            source: PCMVolumeTransformer = await asyncio.to_thread(build_audio, gp_state.volume, ffmpeg_source, stderr_buf, opts=gp_state.song_mods)
            gp_state.play_audio(source,stderr_buf,self.bot,song.webpage_url)
            next_song = gp_state.songs_list[1] if len(gp_state.songs_list) >= 2 else None
            await reply(interaction, embed=song.return_embed(next_song))
        else:
            await reply(interaction,embed=gp_state.songs_list[0].return_err_embed())
            if len(gp_state.songs_list) >= 2:
                await gp_state.helper_play_next(gp_state.guild_id,self.bot)
        return ffmpeg_source

    async def _queue_helper(self, interaction: discord.Interaction, query:str, gp_state: GuildPlaybackState) -> Song|None:
        if not(song_info := await get_Song_Info(query)):
            await reply(interaction, embed=txt_only_embed("Invalid link or song"))
            return None
        if isinstance(song_info, Playlist):
            gp_state.songs_list.extend(song_info.songs)
        elif isinstance(song_info, Song):
            gp_state.songs_list.append(song_info)
        next_song = gp_state.songs_list[1] if len(gp_state.songs_list) >= 2 else None
        if isinstance(song_info, Playlist):
            await reply(interaction, embed=song_info.return_embed())
            song_info = song_info.songs[0]
        else:
            await reply(interaction, embed=song_info.return_embed(queued=True,next_song=next_song))
        return song_info

    @app_commands.command(name="play", description="Enter song name or song url")
    @app_commands.describe(query="Currently does not support soundcloud playlists")
    @commands.max_concurrency(1, wait=True)
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        if not(g_id:=interaction.guild_id):
            return None
        await interaction.response.defer()
        vc = await join_vc(interaction)
        if not isinstance(vc, VoiceClient):
            return None
        gp_state = self.guildpback_dict[g_id]
        gp_state.text_channel = interaction.channel if isinstance(interaction.channel, TextChannel) else None
        song_info = await self._queue_helper(interaction,query,gp_state)
        if song_info:
            if gp_state.vc and gp_state.vc.is_playing():
                await gp_state.override_task()
                return None
            ffmpeg_source = await self._start_playback(interaction,song_info,gp_state)
            gp_state.cache_task = asyncio.create_task(gp_state.cache_songs(song_info,ffmpeg_source))
        return None


    @app_commands.command(name="queue", description="Gets song queue")
    async def queue(self, interaction: discord.Interaction) -> None:
        if not (gp_state := self.return_gp_state(interaction)):
            return None
        if not gp_state.songs_list:
            await reply(interaction, embed=txt_only_embed("Queue empty!"))
            return None
        queue_playlist = Playlist(gp_state.songs_list)
        view = QueueView(QueueEmbed(queue_playlist,gp_state.song_loop,gp_state.nightcore),self)
        if view.queueEmbed.embed:
            await interaction.response.send_message(embed=view.queueEmbed.embed,view=view,file=gen_bot_thumbnail())
            view.message = await interaction.original_response()
        return None

    @app_commands.command(name="skip", description="Skips current song")
    async def skip(self, interaction: discord.Interaction) -> None:
        if not (gp_state := self.return_gp_state(interaction)):
            return None
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

    async def _shuffle_queue(self, interaction: discord.Interaction) -> None:
        if not (gp_state := self.return_gp_state(interaction)):
            return None
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

    @app_commands.command(name="shuffle", description="Shuffles the queue")
    async def _shuffle(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await self._shuffle_queue(interaction)

    @app_commands.command(name="loop", description="Loop current song")
    async def loopSong(self, interaction: discord.Interaction) -> None:
        if not (gp_state := self.return_gp_state(interaction)):
            return None
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
        if not (gp_state := self.return_gp_state(interaction)):
            return None
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
        if not (gp_state := self.return_gp_state(interaction)):
            return None
        if not gp_state.vc:
            await reply(interaction, embed=txt_only_embed("Not in a voice channel!"))
            return None
        await gp_state.voice_cleanup(leave_vc=True)
        await reply(interaction, embed=txt_only_embed("Stopping playblack..."))
        return None

    @app_commands.command(name="clear", description="Clears music queue")
    async def clear(self, interaction: discord.Interaction) -> None:
        if not (gp_state := self.return_gp_state(interaction)):
            return None
        if not (guild := interaction.guild):
            return None
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
        if not (gp_state := self.return_gp_state(interaction)):
            return None
        if gp_state.source:
            gp_state.source.volume = volume
        gp_state.volume = volume
        await reply(interaction, embed=txt_only_embed(f"Set volume to: {gp_state.volume}"))
        return None

    async def _night_core(self, interaction: discord.Interaction):
        if not (gp_state := self.return_gp_state(interaction)):
            return None
        if not gp_state.nightcore:
            await self.mod_song(interaction,"pitch" ,1.25)
            await reply(interaction, embed=txt_only_embed("Nightcore on!🙀"))
        else:
            await self.mod_song(interaction, "off", 1)
            await reply(interaction, embed=txt_only_embed("Nightcore off!😿"))
        gp_state.nightcore = not gp_state.nightcore
        return None

    @app_commands.command(name="night-core", description="Toggle night-core")
    async def night_core(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._night_core(interaction)
        return None

    async def mod_song(self, interaction: discord.Interaction, mod_type: Literal["pitch","speed","off"], effect_strength: app_commands.Range[float,0.0,2.0]) -> None:
        if not (gp_state := self.return_gp_state(interaction)):
            return None
        if mod_type == "pitch":
            gp_state.song_mods = f",aresample=48000,asetrate=48000*{effect_strength},aresample=48000"
        elif mod_type == "speed":
            gp_state.song_mods = f",atempo={effect_strength}"
        elif mod_type == "off":
            gp_state.song_mods = ""
        if gp_state.vc and gp_state.vc.is_playing():
            gp_state.mod_mid_song = True
            gp_state.songs_list.insert(1,gp_state.songs_list[0])
            if gp_state.start_time:
                gp_state.seek_time = time.monotonic() - gp_state.start_time
            gp_state.vc.stop()
        return None

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MikuMusicCommands(bot))
