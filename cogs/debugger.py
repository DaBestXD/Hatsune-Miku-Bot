import logging
import discord
from discord.ext.commands.cog import Cog
from audio_utils.guildstate_controller import GuildStateController
from botextras.constants import GUILD_OBJECT
from botextras.bot_funcs_ext import owner_command, reply, text_only_embed,code_block_embed
from discord.ext import commands
from discord import Interaction, app_commands
from audio_utils.audio_class import Song
from cogs.musicplayer import MikuMusicCommands

class botDebugger(commands.Cog):
    """
    Bot debugging commandsn
    Cogname: debugger
    """
    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.logger = logging.getLogger(__class__.__name__)


    @app_commands.command(name="cog_reload", description="Reloads a cog")
    @app_commands.guilds(GUILD_OBJECT)
    @app_commands.guild_only()
    @owner_command()
    async def reload_cog(self, interaction: Interaction, cog_name: str):
        if not cog_name in self.bot.extensions:
            await reply(interaction, embed=text_only_embed("🙀"))
            return None
        await self.bot.reload_extension(cog_name)
        await reply(interaction, embed=text_only_embed(f"Reloading {cog_name}"))
        return None

    @reload_cog.autocomplete("cog_name")
    async def cog_ext_name_autocomplete(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        return [app_commands.Choice(name=s,value=s) for s in self.bot.extensions]

    def return_commands_embed(self,cog: Cog) -> discord.Embed:
        return code_block_embed(txt=[i.name for i in cog.__cog_app_commands__],title=cog.__class__.__name__)

    def return_guild_state_embed(self, gp_con: GuildStateController, guild_name: str) -> discord.Embed:
        state = gp_con.state
        active_song = state.active_song.title if state.active_song else "None"
        next_song = state.songs[1].title if len(state.songs) >= 2 else "None"
        preview_songs = [
            song.title for song in state.songs[:5] if isinstance(song, Song)
        ]
        queue_preview = "\n".join(
            f"{idx}. {title}" for idx, title in enumerate(preview_songs)
        ) or "Queue empty"
        mods = state.song_mods if state.song_mods else "None"
        if len(mods) > 120:
            mods = mods[:117] + "..."

        embed = discord.Embed(
            title=f"Music info for {guild_name}",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="Playback",
            value=(
                f"Active: `{active_song}`\n"
                f"Next: `{next_song}`\n"
                f"Loop: `{state.song_loop}`\n"
                f"Nightcore: `{state.nightcore}`\n"
                f"Volume: `{state.volume:.2f}`"
            ),
            inline=False,
        )
        embed.add_field(
            name="State",
            value=(
                f"Queued songs: `{len(state.songs)}`\n"
                f"Cached sources: `{len(state.song_cache)}`\n"
                f"Seek time: `{state.seek_time}`\n"
                f"Start time: `{state.start_time}`\n"
                f"Voice connected: `{state.vc is not None}`"
            ),
            inline=False,
        )
        embed.add_field(
            name="Channels",
            value=(
                f"Text channel: `{getattr(state.text_channel, 'name', None)}`\n"
                f"Voice channel: `{getattr(getattr(state.vc, 'channel', None), 'name', None)}`"
            ),
            inline=False,
        )
        embed.add_field(name="Song Mods", value=f"`{mods}`", inline=False)
        embed.add_field(name="Queue Preview", value=queue_preview, inline=False)
        return embed


    @app_commands.command(name="dump_cog_info", description="Reloads a cog")
    @app_commands.guilds(GUILD_OBJECT)
    @app_commands.guild_only()
    @owner_command()
    async def dump_cog_info(self,interaction: Interaction, cog_class_name: str):
        if not (ext_cog := self.bot.get_cog(cog_class_name)):
            await reply(interaction,embed=text_only_embed("🙀"))
            return None
        if not(g_id := interaction.guild_id):
            return None
        list_embeds: list[discord.Embed] = []
        list_embeds.append(self.return_commands_embed(ext_cog))
        if isinstance(ext_cog, MikuMusicCommands):
            gp_con = await ext_cog.return_gp_con(g_id)
            guild_name = guild.name if (guild := self.bot.get_guild(g_id)) else str(g_id)
            list_embeds.append(self.return_guild_state_embed(gp_con, guild_name))
        for e in list_embeds:
            await reply(interaction, embed=e)
        return None

    @dump_cog_info.autocomplete("cog_class_name")
    async def cog_name_autocomplete(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        cog_class_names = [s.__class__.__name__ for s in self.bot.cogs.values()]
        return [app_commands.Choice(name=s,value=s) for s in cog_class_names]

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(botDebugger(bot))
