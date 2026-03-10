import logging
from time import sleep
import discord
from discord.ext.commands.cog import Cog
from audio_utils.guild_playback_state import GuildPlaybackState
from botextras.constants import GUILD_OBJECT,INVIS_CHAR
from botextras.bot_funcs_ext import owner_command, reply, gen_bot_thumbnail, txt_only_embed
from discord.ext import commands
from discord import Interaction, app_commands

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
    @owner_command()
    async def reload_cog(self, interaction: Interaction, cog_name: str):
        if not cog_name in self.bot.extensions:
            await reply(interaction, embed=txt_only_embed("🙀"))
            return None
        await self.bot.reload_extension(cog_name)
        await reply(interaction, embed=txt_only_embed(f"Reloading {cog_name}"))
        return None

    @reload_cog.autocomplete("cog_name")
    async def cog_ext_name_autocomplete(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        return [app_commands.Choice(name=s,value=s) for s in self.bot.extensions]

    def return_commands_embed(self,cog: Cog) -> discord.Embed:
        embed = discord.Embed(title=f"{cog.__class__.__name__} commands")
        body_text: list[str] = ["```"]
        for i in cog.__cog_app_commands__:
            body_text.append(i.name)
        body_text.append("```")
        embed.add_field(name=INVIS_CHAR,value="\n".join(body_text))
        return embed

    def return_guild_playbackstate(self, gp_state: GuildPlaybackState):
        return "\n".join(gp_state.class_info())

    @app_commands.command(name="dump_cog_info", description="Reloads a cog")
    @app_commands.guilds(GUILD_OBJECT)
    @owner_command()
    async def dump_cog_info(self,interaction: Interaction, cog_class_name: str):
        if not (ext_cog := self.bot.get_cog(cog_class_name)):
            await reply(interaction,embed=txt_only_embed("🙀"))
            return None
        list_embeds: list[discord.Embed] = []
        list_embeds.append(self.return_commands_embed(ext_cog))
        if isinstance(ext_cog, MikuMusicCommands):
            embed = discord.Embed(title=f"Music info")
            for k,v in ext_cog.guildpback_dict.items():
                embed.add_field(name=self.bot.get_guild(k),value=self.return_guild_playbackstate(v))
            list_embeds.append(embed)
        for e in list_embeds:
            await reply(interaction, embed=e)
            sleep(0.5)

    @dump_cog_info.autocomplete("cog_class_name")
    async def cog_name_autocomplete(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        cog_class_names = [s.__class__.__name__ for s in self.bot.cogs.values()]
        return [app_commands.Choice(name=s,value=s) for s in cog_class_names]

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(botDebugger(bot))
