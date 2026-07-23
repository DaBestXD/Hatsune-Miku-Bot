from __future__ import annotations

import logging
from typing import override

from aiohttp import ClientSession, ClientTimeout
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

from hatsune_miku_bot.audio.audio_resolver import AudioInfoResolver
from hatsune_miku_bot.audio.guild_state_controller import (
    GuildStateController,
)
from hatsune_miku_bot.audio.playback_helpers import join_vc
from hatsune_miku_bot.audio.queue_view import QueueEmbed, QueueView
from hatsune_miku_bot.db_logging.db_main import DBLogic
from hatsune_miku_bot.utils.discord_helpers import (
    code_block_embed,
    gen_bot_thumbnail,
    reply,
    text_only_embed,
)

logger = logging.getLogger(__name__)


class MikuMusicCommands(commands.Cog):
    """
    Stores all the music slash commands
    Cogname: musicplayer
    """

    def __init__(self, bot: commands.Bot, db_logic: DBLogic) -> None:
        self.bot: commands.Bot = bot
        self.guildstate_con_dict: dict[int, GuildStateController] = {}
        self.synced: bool = False
        self.audio_session: ClientSession | None = None
        self.audio_info_resolver: AudioInfoResolver | None = None
        self.db_logic = db_logic

    @override
    async def cog_load(self) -> None:
        """
        Cog loading and unloading would only be caused by debugging commands
        """
        if not self.audio_session:
            logger.debug(
                "Creating audio HTTP session",
                extra={"event": "audio_http_session_creation_started"},
            )
            self.audio_session = ClientSession(timeout=ClientTimeout(total=10))
            self.audio_info_resolver = AudioInfoResolver(self.audio_session)
        else:
            logger.debug(
                "Audio HTTP session was already created",
                extra={"event": "audio_http_session_already_created"},
            )

    @override
    async def cog_unload(self) -> None:
        controllers = tuple(self.guildstate_con_dict.values())
        self.guildstate_con_dict.clear()
        for controller in controllers:
            try:
                await controller.stop()
            except Exception:
                logger.exception(
                    "Failed to stop guild controller %d during cog unload",
                    controller.id,
                    extra={
                        "event": "guild_controller_stop_failed",
                        "guild_id": controller.id,
                    },
                )

        if self.audio_session and not self.audio_session.closed:
            logger.debug(
                "Closing audio HTTP session",
                extra={"event": "audio_http_session_closing"},
            )
            await self.audio_session.close()
            self.audio_info_resolver = None
        else:
            logger.debug(
                "Audio HTTP session was already closed",
                extra={"event": "audio_http_session_already_closed"},
            )

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: Guild) -> None:
        logger.info(
            "Removed guild controller for %s[%d]",
            guild.name,
            guild.id,
            extra={
                "event": "guild_controller_removed",
                "guild_id": guild.id,
            },
        )
        con = self.guildstate_con_dict.pop(guild.id, None)
        if con:
            await con.stop()
        return None

    @commands.Cog.listener()
    async def on_guild_join(self, guild: Guild) -> None:
        logger.info(
            "Added guild controller for %s[%d]",
            guild.name,
            guild.id,
            extra={
                "event": "guild_controller_added",
                "guild_id": guild.id,
            },
        )
        self.guildstate_con_dict[guild.id] = GuildStateController(
            self.bot, guild.id, self.db_logic
        )
        await self.guildstate_con_dict[guild.id].run()
        return None

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if not self.synced:
            for g in self.bot.guilds:
                self.guildstate_con_dict[g.id] = GuildStateController(
                    self.bot, g.id, self.db_logic
                )
                await self.guildstate_con_dict[g.id].run()
                logger.info(
                    "Initialized guild playback state for %s[%d]",
                    g.name,
                    g.id,
                    extra={
                        "event": "guild_playback_state_initialized",
                        "guild_id": g.id,
                    },
                )
            self.synced = True
        else:
            logger.debug(
                "Guild playback state was already initialized",
                extra={"event": "guild_playback_state_already_initialized"},
            )
        return None

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: Member, before: VoiceState, after: VoiceState
    ) -> None:
        if not self.bot.user or member.id != self.bot.user.id:
            return None
        con = self.guildstate_con_dict.get(member.guild.id)
        if not con:
            logger.debug(
                "Ignoring voice state update for guild %d without a controller",
                member.guild.id,
                extra={
                    "event": "voice_state_update_controller_missing",
                    "guild_id": member.guild.id,
                },
            )
            return None
        if not before.channel and after.channel:
            logger.debug(
                "Bot has joined the voice channel: %s at [%s]",
                after.channel,
                member.guild.name,
                extra={
                    "event": "bot_voice_channel_joined",
                    "guild_id": member.guild.id,
                    "channel_id": getattr(after.channel, "id", None),
                },
            )
            if isinstance(member.guild.voice_client, VoiceClient):
                con.state.vc = member.guild.voice_client
            return None
        if before.channel and not after.channel:
            logger.debug(
                "Bot has left the voice channel: %s at [%s]",
                before.channel,
                member.guild.name,
                extra={
                    "event": "bot_voice_channel_left",
                    "guild_id": member.guild.id,
                    "channel_id": getattr(before.channel, "id", None),
                },
            )
            con.state.vc = None
            return None
        if before.channel != after.channel:
            logger.debug(
                "Bot has moved from %s to %s at [%s]",
                before.channel,
                after.channel,
                member.guild.name,
                extra={
                    "event": "bot_voice_channel_moved",
                    "guild_id": member.guild.id,
                    "previous_channel_id": (
                        getattr(before.channel, "id", None)
                        if before.channel
                        else None
                    ),
                    "channel_id": (
                        getattr(after.channel, "id", None)
                        if after.channel
                        else None
                    ),
                },
            )
            if isinstance(member.guild.voice_client, VoiceClient):
                con.state.vc = member.guild.voice_client
        return None

    @app_commands.command(
        name="play", description="Enter song name or song url"
    )
    @app_commands.describe(
        query="Currently does not support soundcloud playlists"
    )
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
        audio_resolver = self.audio_info_resolver
        if not audio_resolver:
            logger.error(
                "Audio information resolver was never created",
                extra={
                    "event": "audio_info_resolver_missing",
                    "guild_id": guild_id,
                },
            )
            return None
        result = await audio_resolver.get_song_info(query)
        if not result:
            await reply(
                interaction,
                embed=text_only_embed(f"Error trying to play {query}"),
            )
            return None

        if not isinstance(interaction.channel, TextChannel):
            await reply(
                interaction,
                embed=text_only_embed("Can only be used in text channel!"),
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
            return None
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
    async def loop_song(self, interaction: Interaction) -> None:
        """
        Usage /loop Loops current song
        """
        if not (guild_id := interaction.guild_id):
            return None
        await interaction.response.defer()
        gp_con = self.guildstate_con_dict[guild_id]
        await gp_con.add_event(gp_con.loop_song, interaction)

    @app_commands.command(name="loop-all", description="Loop current queue")
    @app_commands.guild_only()
    async def loop_song_all(self, interaction: Interaction) -> None:
        """
        Usage /loop Loops current queue
        """
        if not (guild_id := interaction.guild_id):
            return None
        await interaction.response.defer()
        gp_con = self.guildstate_con_dict[guild_id]
        await gp_con.add_event(gp_con.loop_all, interaction)

    @app_commands.command(name="remove", description="Remove song from queue")
    @app_commands.describe(index="Must be a valid number to remove")
    @app_commands.guild_only()
    async def remove_from_queue(
        self, interaction: Interaction, index: int
    ) -> None:
        """
        Usage /remove [index] Removes song at index from queue
        """
        if not (guild_id := interaction.guild_id):
            return None
        await interaction.response.defer()
        gp_con = self.guildstate_con_dict[guild_id]
        await gp_con.add_event(gp_con.remove_from_queue, interaction, index)
        return None

    @app_commands.command(
        name="stop", description="Disconnects bot from voice channel"
    )
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
        await reply(
            interaction, embed=text_only_embed(f"Set volume to: {volume}")
        )
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

    @app_commands.command(
        name="bass-boost", description="Set bass of song to value"
    )
    @app_commands.describe(
        effect_strength="Warning most values over 20 will distort sound(default value is 0)",  # noqa: E501
    )
    @app_commands.guild_only()
    async def bass_boost(
        self, interaction: Interaction, effect_strength: float
    ):
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
        name="speed", description="Change the song speed from 0.5 -> 2.0"
    )
    @app_commands.describe(
        effect_strength="Select a value between 0.5 -> 2.0(default value is 1)"
    )
    @app_commands.guild_only()
    async def speed(
        self,
        interaction: Interaction,
        effect_strength: app_commands.Range[float, 0.5, 2.0],
    ):
        """
        Usage /speed [0.5, 2.0]
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

    @app_commands.command(
        name="song-tracker",
        description="Returns the song ranking for this server",
    )
    @app_commands.guild_only()
    async def song_tracker(self, interaction: Interaction):
        if not (guild_id := interaction.guild_id):
            return None
        await interaction.response.defer()
        gp_con = self.guildstate_con_dict[guild_id]
        songs = await gp_con.db_logic.rank_song_per_guild(guild_id)
        # TODO: messy for now just fix later, just for prototyping
        # something something char limit fix later
        _str_songs = [
            f"{position}. {title}: {total_plays} plays"
            for position, (title, total_plays) in enumerate(songs, start=1)
        ]
        if not _str_songs:
            await reply(
                interaction,
                embed=text_only_embed(
                    "No songs played yet, go play some songs first!"
                ),
            )
            return None

        embed = code_block_embed(_str_songs, "Most songs played")
        await reply(interaction, embed=embed)
        return None
