from __future__ import annotations
import logging
from discord import (
    Guild,
    Interaction,
    Member,
    TextChannel,
    VoiceClient,
    VoiceState,
    app_commands,
)
from discord.ext import commands
from hatsune_miku_bot.audio_utils.audio_handler import get_Song_Info
from hatsune_miku_bot.audio_utils.guildstate_controller import (
    GuildStateController,
)
from hatsune_miku_bot.audio_utils.music_queue_classes import QueueEmbed, QueueView
from hatsune_miku_bot.audio_utils.bot_audio_functions import join_vc
from hatsune_miku_bot.botextras.bot_funcs_ext import (
    gen_bot_thumbnail,
    reply,
    text_only_embed,
)


class MikuMusicCommands(commands.Cog):
    """
    Stores all the music slash commands
    Cogname: musicplayer
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.bot: commands.Bot = bot
        self.guildstate_con_dict: dict[int, GuildStateController] = {}
        self.synced: bool = False

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: Guild) -> None:
        self.logger.info(
            "Removed %s[%d] from Guildstate Controller Dictionary", guild.name, guild.id
        )
        con = self.guildstate_con_dict.pop(guild.id, None)
        if con:
            await con.stop()
        return None

    @commands.Cog.listener()
    async def on_guild_join(self, guild: Guild) -> None:
        self.logger.info(
            "Added %s[%d] to Guildstate Controller Dictionary", guild.name, guild.id
        )
        self.guildstate_con_dict[guild.id] = GuildStateController(self.bot, guild.id)
        await self.guildstate_con_dict[guild.id].run()
        return None

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if not self.synced:
            for g in self.bot.guilds:
                self.guildstate_con_dict[g.id] = GuildStateController(self.bot, g.id)
                await self.guildstate_con_dict[g.id].run()
                self.logger.info("Added %s[%d] to GuildPlaybackState", g.name, g.id)
            self.synced = True
        else:
            self.logger.debug("GuildPlaybackState dict already initialized")
        return None

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: Member, before: VoiceState, after: VoiceState
    ) -> None:
        if not self.bot.user:
            return None
        con = self.guildstate_con_dict[member.guild.id]
        if not before.channel and after.channel:
            self.logger.debug(
                "Bot has joined the voice channel: %s at [%s]",
                after.channel,
                member.guild.name,
            )
            if isinstance(member.guild.voice_client, VoiceClient):
                con.state.vc = member.guild.voice_client
            return None
        if before.channel and not after.channel:
            self.logger.debug(
                "Bot has left the voice channel: %s at [%s]",
                before.channel,
                member.guild.name,
            )
            con.state.vc = None
            return None
        if before.channel != after.channel:
            self.logger.debug(
                "Bot has moved from %s to %s at [%s]",
                before.channel,
                after.channel,
                member.guild.name,
            )
            if isinstance(member.guild.voice_client, VoiceClient):
                con.state.vc = member.guild.voice_client
        return None

    @app_commands.command(name="play", description="Enter song name or song url")
    @app_commands.describe(query="Currently does not support soundcloud playlists")
    @app_commands.guild_only()
    async def play(self, interaction: Interaction, query: str):
        """
        Usage /play [query]
        """
        await interaction.response.defer()
        if not (guild_id := interaction.guild_id):
            return None
        if not isinstance(vc := await join_vc(interaction), VoiceClient):
            return None
        result = await get_Song_Info(query)
        if not result:
            await reply(
                interaction, embed=text_only_embed(f"Error trying to play {query}")
            )
            return None

        if not isinstance(interaction.channel, TextChannel):
            await reply(
                interaction, embed=text_only_embed("Can only be used in text channel!")
            )
            return None
        gp_con = self.guildstate_con_dict[guild_id]
        await gp_con.add_event(gp_con.queue_songs, interaction, result, vc)
        await gp_con.add_event(gp_con.begin_playback)
        return None

    @app_commands.command(name="queue", description="Gets song queue")
    @app_commands.guild_only()
    async def queue(self, interaction: Interaction) -> None:
        """
        Usage /queue Displays current music queue
        """
        interaction.guild
        if not (guild_id := interaction.guild_id):
            return None
        gp_con = self.guildstate_con_dict[guild_id]
        if not gp_con.state.songs:
            await reply(interaction, embed=text_only_embed("Queue empty!"))
            return None
        view = QueueView(QueueEmbed(gp_con), self)
        if view.queueEmbed.embed:
            await interaction.response.send_message(
                embed=view.queueEmbed.embed, view=view, file=gen_bot_thumbnail()
            )
            view.message = await interaction.original_response()
        return None

    @app_commands.command(name="skip", description="Skips current song")
    @app_commands.guild_only()
    async def skip(self, interaction: Interaction) -> None:
        """
        Usage /skip Skips current song
        """
        await interaction.response.defer()
        if not (guild_id := interaction.guild_id):
            return None
        vc = await join_vc(interaction, join=False)
        if not vc:
            return None
        gp_con = self.guildstate_con_dict[guild_id]
        if not gp_con.state.songs:
            await reply(interaction, embed=text_only_embed("Queue empty!"))
        await gp_con.add_event(gp_con.skip, interaction)
        return None

    @app_commands.command(name="shuffle", description="Shuffles the queue")
    @app_commands.guild_only()
    async def shuffle(self, interaction: Interaction) -> None:
        """
        Usage /shuffle Shuffles music queue
        """
        if not (guild_id := interaction.guild_id):
            return None
        await interaction.response.defer()
        gp_con = self.guildstate_con_dict[guild_id]
        await gp_con.add_event(gp_con.shuffle, interaction)
        return None

    @app_commands.command(name="loop", description="Loop current song")
    @app_commands.guild_only()
    async def loopSong(self, interaction: Interaction) -> None:
        """
        Usage /loop Loops current song
        """
        if not (guild_id := interaction.guild_id):
            return None
        await interaction.response.defer()
        gp_con = self.guildstate_con_dict[guild_id]
        await gp_con.add_event(gp_con.loop_song, interaction)

    @app_commands.command(name="remove", description="Remove song from queue")
    @app_commands.describe(index="Must be a valid number to remove")
    @app_commands.guild_only()
    async def removeFromQueue(self, interaction: Interaction, index: int) -> None:
        """
        Usage /remove [index] Removes song at index from queue
        """
        if not (guild_id := interaction.guild_id):
            return None
        await interaction.response.defer()
        gp_con = self.guildstate_con_dict[guild_id]
        await gp_con.add_event(gp_con.remove_from_queue, interaction, index)
        return None

    @app_commands.command(name="stop", description="Disconnects bot from voice channel")
    @app_commands.guild_only()
    async def stop(self, interaction: Interaction) -> None:
        """
        Usage /stop Clears the music queue and disconnects bot from call
        """
        if not (guild_id := interaction.guild_id):
            return None
        await interaction.response.defer()
        gp_con = self.guildstate_con_dict[guild_id]
        await gp_con.add_event(gp_con.stop_playback, interaction)
        return None

    @app_commands.command(name="clear", description="Clears music queue")
    @app_commands.guild_only()
    async def clear(self, interaction: Interaction) -> None:
        """
        Usage /clear Clears the current music queue
        """
        if not (guild_id := interaction.guild_id):
            return None
        await interaction.response.defer()
        gp_con = self.guildstate_con_dict[guild_id]
        await gp_con.add_event(gp_con.clear_queue, interaction)
        return None

    @app_commands.command(
        name="volume", description="Change the volume from 0.00 -> 2.00"
    )
    @app_commands.describe(volume="Select a value between 0-2")
    @app_commands.guild_only()
    async def set_volume(
        self,
        interaction: Interaction,
        volume: app_commands.Range[float, 0.0, 2.0],
    ) -> None:
        """
        Usage /set_volume [0.0-2.0] Set volume between 0-2
        """
        if not (guild_id := interaction.guild_id):
            return None
        await interaction.response.defer()
        gp_con = self.guildstate_con_dict[guild_id]
        await gp_con.add_event(gp_con.change_volume, volume)
        await reply(interaction, embed=text_only_embed(f"Set volume to: {volume}"))
        return None

    @app_commands.command(name="night-core", description="Toggle night-core")
    @app_commands.guild_only()
    async def night_core(self, interaction: Interaction):
        """
        Usage /night_core Toggles nightcore on
        """
        if not (guild_id := interaction.guild_id):
            return None
        await interaction.response.defer()
        gp_con = self.guildstate_con_dict[guild_id]
        if not gp_con.state.songs:
            await reply(interaction, embed=text_only_embed("Queue empty!"))
            return None
        if not isinstance(await join_vc(interaction, join=False), VoiceClient):
            return None
        await gp_con.add_event(gp_con.nightcore, interaction)
        return None

    @app_commands.command(name="bass-boost", description="Set bass of song to value")
    @app_commands.describe(
        effect_strength="Warning most values over 20 will distort sound(default value is 0)"
    )
    @app_commands.guild_only()
    async def bass_boost(self, interaction: Interaction, effect_strength: float):
        """
        Usage /bass-boost [float]
        """
        if not (guild_id := interaction.guild_id):
            return None
        await interaction.response.defer()
        gp_con = self.guildstate_con_dict[guild_id]
        if not gp_con.state.songs:
            await reply(interaction, embed=text_only_embed("Queue empty!"))
            return None
        if not isinstance(await join_vc(interaction, join=False), VoiceClient):
            return None
        await gp_con.add_event(gp_con.set_bass, interaction, effect_strength)
        return None

    @app_commands.command(
        name="speed", description="Change the song speed from 00.1 -> 2.0"
    )
    @app_commands.describe(
        effect_strength="Select a value between 0.01 -> 2.0(default value is 1)"
    )
    @app_commands.guild_only()
    async def speed(
        self,
        interaction: Interaction,
        effect_strength: app_commands.Range[float, 0.01, 2.0],
    ):
        """
        Usage /speed [0.01, 2.0]
        """
        if not (guild_id := interaction.guild_id):
            return None
        await interaction.response.defer()
        gp_con = self.guildstate_con_dict[guild_id]
        if not gp_con.state.songs:
            await reply(interaction, embed=text_only_embed("Queue empty!"))
            return None
        if not isinstance(await join_vc(interaction, join=False), VoiceClient):
            return None
        await gp_con.add_event(gp_con.set_speed, interaction, effect_strength)
        return None


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MikuMusicCommands(bot))
