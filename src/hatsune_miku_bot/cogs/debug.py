import logging

import discord
from discord import Interaction, app_commands
from discord.ext import commands

from hatsune_miku_bot.audio.audio_resolver import Song
from hatsune_miku_bot.audio.guild_state_controller import GuildStateController
from hatsune_miku_bot.bot_config.constants import GUILD_OBJECT
from hatsune_miku_bot.cogs.music import MikuMusicCommands
from hatsune_miku_bot.utils.discord_helpers import (
    code_block_embed,
    owner_command,
    reply,
    text_only_embed,
)


class BotDebugger(commands.Cog):
    """
    Bot debugging commandsn
    Cogname: debugger
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.logger = logging.getLogger(self.__class__.__name__)

    @app_commands.command(name="cog_reload", description="Reloads a cog")
    @app_commands.guilds(GUILD_OBJECT)
    @app_commands.guild_only()
    @owner_command()
    async def reload_cog(self, interaction: Interaction, cog_name: str):
        if cog_name not in self.bot.extensions:
            await reply(interaction, embed=text_only_embed("🙀"))
            return None
        await self.bot.reload_extension(cog_name)
        await reply(interaction, embed=text_only_embed(f"Reloading {cog_name}"))
        return None

    @reload_cog.autocomplete("cog_name")
    async def cog_ext_name_autocomplete(
        self, interaction: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return [app_commands.Choice(name=s, value=s) for s in self.bot.extensions]

    def return_commands_embed(self, cog: commands.Cog) -> discord.Embed:
        return code_block_embed(
            txt=[i.name for i in cog.__cog_app_commands__],
            title=cog.__class__.__name__,
        )

    def return_guild_state_embed(
        self, gp_con: GuildStateController, guild_name: str
    ) -> discord.Embed:
        gp_con.state
        embed = discord.Embed(
            title=f"Music info for {guild_name}",
            color=discord.Color.blue(),
        )
        next_song = gp_con.state.songs[1] if len(gp_con.state.songs) else None
        embed.add_field(
            name="Playback",
            value=(
                f"Active: `{gp_con.state.active_song}`\n"
                f"Next: `{next_song}`\n"
                f"Loop: `{gp_con.state.song_mods.song_loop}`\n"
                f"Nightcore: `{gp_con.state.song_mods.is_nightcore()}`\n"
                f"Volume: `{gp_con.state.song_mods.volume}`"
            ),
            inline=False,
        )
        embed.add_field(
            name="State",
            value=(
                f"Queued songs: `{len(gp_con.state.songs)}`\n"
                f"Cached sources: `{len(gp_con.state.song_cache)}`\n"
                f"Seek time: `{gp_con.state.song_mods.position_offset_s}`\n"
                f"Start time: `{gp_con.state.song_mods.start_timestamp}`\n"
                f"Voice connected: `{gp_con.state.vc is not None}`"
            ),
            inline=False,
        )
        embed.add_field(
            name="Channels",
            value=(
                f"Text channel: `{getattr(gp_con.state.text_channel, 'name', None)}`\n"
                f"Voice channel: `{getattr(getattr(gp_con.state.vc, 'channel', None), 'name', None)}`"  # noqa: E501
            ),
            inline=False,
        )
        embed.add_field(
            name="Song Mods",
            value=f"`{gp_con.state.song_mods.song_pitch, gp_con.state.song_mods.song_speed, gp_con.state.song_mods.song_bass}`",
            inline=False,
        )
        preview_songs = [
            song.title for song in gp_con.state.songs[:5] if isinstance(song, Song)
        ]
        queue_preview = (
            "\n".join(f"{idx}. {title}" for idx, title in enumerate(preview_songs))
            or "Queue empty"
        )
        embed.add_field(name="Queue Preview", value=queue_preview, inline=False)
        return embed

    @app_commands.command(name="dump_cog_info", description="Reloads a cog")
    @app_commands.guilds(GUILD_OBJECT)
    @app_commands.guild_only()
    @owner_command()
    async def dump_cog_info(self, interaction: Interaction, cog_class_name: str):
        if not (ext_cog := self.bot.get_cog(cog_class_name)):
            await reply(interaction, embed=text_only_embed("🙀"))
            return None
        if not (guild_id := interaction.guild_id):
            return None
        list_embeds: list[discord.Embed] = []
        list_embeds.append(self.return_commands_embed(ext_cog))
        if isinstance(ext_cog, MikuMusicCommands):
            gp_con = ext_cog.guildstate_con_dict[guild_id]
            guild_name = (
                guild.name if (guild := self.bot.get_guild(guild_id)) else str(guild_id)
            )
            list_embeds.append(self.return_guild_state_embed(gp_con, guild_name))
        for e in list_embeds:
            await reply(interaction, embed=e)
        return None

    @dump_cog_info.autocomplete("cog_class_name")
    async def cog_name_autocomplete(
        self, interaction: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        cog_class_names = [s.__class__.__name__ for s in self.bot.cogs.values()]
        return [app_commands.Choice(name=s, value=s) for s in cog_class_names]


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BotDebugger(bot))
