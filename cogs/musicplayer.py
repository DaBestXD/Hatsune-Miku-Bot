from __future__ import annotations
import logging
import discord
from discord import (Guild, Interaction, Member, TextChannel,
    VoiceClient,VoiceState,app_commands)
from discord.ext import commands
from audio_utils.audio_class import Playlist
from audio_utils.audio_handler import get_Song_Info
from audio_utils.guildstate_controller import GuildStateController, QueueSongs, Skip
from audio_utils.music_queue_classes import QueueEmbed, QueueView
from audio_utils.bot_audio_functions import join_vc
from botextras.bot_events import (ClearQueue, LoopSong, Nightcore,
    RemoveFromQueue, Shuffle, StopPlayblack, UpdateVoiceStatus, VolumeControl)
from botextras.bot_funcs_ext import reply, text_only_embed,gen_bot_thumbnail



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
        self.guildstate_con_dict: dict[int,GuildStateController] = {}
        self.synced: bool = False


    async def return_gp_con(self, g_id: int) -> GuildStateController:
        con = self.guildstate_con_dict.get(g_id)
        if not con:
            con = GuildStateController(self.bot, g_id)
            self.guildstate_con_dict[g_id] = con
        await con.run()
        return con


    @commands.Cog.listener()
    async def on_guild_remove(self, guild: Guild) -> None:
        self.logger.info("Removed %s[%d] from Guildstate Controller Dictionary", guild.name, guild.id)
        self.guildstate_con_dict.pop(guild.id, None)
        return None

    @commands.Cog.listener()
    async def on_guild_join(self, guild: Guild) -> None:
        self.logger.info("Added %s[%d] to Guildstate Controller Dictionary", guild.name, guild.id)
        con = self.guildstate_con_dict.setdefault(guild.id, GuildStateController(self.bot, guild.id))
        await con.run()
        return None

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if not self.synced:
            for g in self.bot.guilds:
                con = self.guildstate_con_dict.setdefault(g.id, GuildStateController(self.bot, g.id))
                await con.run()
                self.logger.info("Added %s[%d] to GuildPlaybackState", g.name, g.id)
            self.synced = True
        else:
            self.logger.info("GuildPlaybackState dict already initialized")
        return None

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: Member, before: VoiceState, after: VoiceState) -> None:
        if not self.bot.user or member.id != self.bot.user.id:
            return None
        con = await self.return_gp_con(member.guild.id)
        if not before.channel and after.channel:
            self.logger.debug("Bot has joined the voice channel: %s at [%s]", after.channel, member.guild.name)
            if isinstance(member.guild.voice_client, VoiceClient):
                await con.add_event(UpdateVoiceStatus(member.guild.voice_client))
            return None
        if before.channel and not after.channel:
            self.logger.debug("Bot has left the voice channel: %s at [%s]", before.channel, member.guild.name)
            await con.add_event(UpdateVoiceStatus(None))
            return None
        if before.channel != after.channel:
            self.logger.debug("Bot has moved from %s to %s at [%s]", before.channel, after.channel, member.guild.name)
        return None


    @app_commands.command(name="play", description="Enter song name or song url")
    @app_commands.describe(query="Currently does not support soundcloud playlists")
    @app_commands.guild_only()
    @commands.max_concurrency(1, wait=True)
    async def play(self,interaction: Interaction, query:str):
        """
        Usage /play [query]
        """
        await interaction.response.defer()
        if not(g_id := interaction.guild_id): return None
        if not isinstance(vc := await join_vc(interaction), VoiceClient):
            return None

        result =  await get_Song_Info(query)

        if not result:
            await reply(interaction,embed=text_only_embed(f"Error trying to play {query}"))
            return None

        songs = result.songs if isinstance(result, Playlist) else [result]
        text_channel = interaction.channel if isinstance(interaction.channel, TextChannel) else None
        if not text_channel:
            await reply(interaction, embed=text_only_embed("Can only be used in text channel!"))
            return None
        gp_con = await self.return_gp_con(g_id)

        if text_channel:
            playlist_check = result if isinstance(result,Playlist) else None
            await gp_con.add_event(QueueSongs(songs,vc,text_channel, interaction,playlist_check))
        return None


    @app_commands.command(name="queue", description="Gets song queue")
    @app_commands.guild_only()
    async def queue(self, interaction: discord.Interaction) -> None:
        """
        Usage /queue Displays current music queue
        """
        if not(g_id := interaction.guild_id): return None
        gp_con = await self.return_gp_con(g_id)
        if not gp_con.state.songs:
            await reply(interaction,embed=text_only_embed("Queue empty!"))
            return None
        view = QueueView(QueueEmbed(gp_con),self)
        if view.queueEmbed.embed:
            await interaction.response.send_message(embed=view.queueEmbed.embed,view=view,file=gen_bot_thumbnail())
            view.message = await interaction.original_response()
        return None

    @app_commands.command(name="skip", description="Skips current song")
    @app_commands.guild_only()
    async def skip(self, interaction: discord.Interaction) -> None:
        """
        Usage /skip Skips current song
        """
        await interaction.response.defer()
        if not(g_id := interaction.guild_id): return None
        vc = await join_vc(interaction,join=False)
        if not vc: return None
        gp_con = await self.return_gp_con(g_id)
        if not gp_con.state.songs:
            await reply(interaction,embed=text_only_embed("Queue empty"))
        await gp_con.add_event(Skip(interaction))

    @app_commands.command(name="shuffle", description="Shuffles the queue")
    @app_commands.guild_only()
    async def shuffle(self, interaction: discord.Interaction) -> None:
        """
        Usage /shuffle Shuffles music queue
        """
        if not(g_id := interaction.guild_id): return None
        await interaction.response.defer()
        gp_con = await self.return_gp_con(g_id)
        await gp_con.add_event(Shuffle(interaction))
        return None

    @app_commands.command(name="loop", description="Loop current song")
    @app_commands.guild_only()
    async def loopSong(self, interaction: discord.Interaction) -> None:
        """
        Usage /loop Loops current song
        """
        if not(g_id := interaction.guild_id): return None
        await interaction.response.defer()
        gp_con = await self.return_gp_con(g_id)
        await gp_con.add_event(LoopSong(interaction,gp_con.state.song_loop))

    @app_commands.command(name="remove", description="Remove song from queue")
    @app_commands.describe(index="Must be a valid number to remove")
    @app_commands.guild_only()
    async def removeFromQueue(self, interaction: discord.Interaction, index: int) -> None:
        """
        Usage /remove [index] Removes song at index from queue
        """
        if not(g_id := interaction.guild_id): return None
        await interaction.response.defer()
        gp_con = await self.return_gp_con(g_id)
        await gp_con.add_event(RemoveFromQueue(interaction,index))
        return None

    @app_commands.command(name="stop", description="Disconnects bot from voice channel")
    @app_commands.guild_only()
    async def stop(self, interaction: discord.Interaction) -> None:
        """
        Usage /stop Clears the music queue and disconnects bot from call
        """
        if not(g_id := interaction.guild_id): return None
        await interaction.response.defer()
        gp_con = await self.return_gp_con(g_id)
        await gp_con.add_event(StopPlayblack(interaction))
        return None

    @app_commands.command(name="clear", description="Clears music queue")
    @app_commands.guild_only()
    async def clear(self, interaction: discord.Interaction) -> None:
        """
        Usage /clear Clears the current music queue
        """
        if not(g_id := interaction.guild_id): return None
        await interaction.response.defer()
        gp_con = await self.return_gp_con(g_id)
        await gp_con.add_event(ClearQueue(interaction))
        return None

    @app_commands.command(name="volume", description="Change the volume from 0.00 -> 2.00")
    @app_commands.describe(volume="Select a value between 0-2")
    @app_commands.guild_only()
    async def set_volume(self, interaction: discord.Interaction, volume: app_commands.Range[float,0.0,2.0]) -> None:
        """
        Usage /set_volume [0.0-2.0] Set volume between 0-2
        """
        if not(g_id := interaction.guild_id): return None
        await interaction.response.defer()
        gp_con = await self.return_gp_con(g_id)
        await gp_con.add_event(VolumeControl(volume))
        await reply(interaction, embed=text_only_embed(f"Set volume to: {volume}"))
        return None


    @app_commands.command(name="night-core", description="Toggle night-core")
    @app_commands.guild_only()
    async def night_core(self, interaction: discord.Interaction):
        """
        Usage /night_core Toggles nightcore on
        """
        if not(g_id := interaction.guild_id): return None
        await interaction.response.defer()
        gp_con = await self.return_gp_con(g_id)
        if not gp_con.state.songs:
            await reply(interaction,embed=text_only_embed("Queue empty!"))
            return None
        if not isinstance(vc := await join_vc(interaction), VoiceClient):
            return None
        await gp_con.add_event(Nightcore(interaction,vc))
        return None



async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MikuMusicCommands(bot))
