import discord
from discord import app_commands
from discord.ext import commands
from botextras.bot_funcs_ext import owner_command,reply,text_only_embed,gen_bot_thumbnail
from botextras.constants import DIS_BOT_THUMBNAIL
from cogs.musicplayer import MikuMusicCommands

class utilCommands(commands.Cog):
    """
    Bot util commands
    Cogname: utilcommands
    """
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="die", description="Turns off bot")
    @app_commands.guild_only()
    @owner_command()
    async def die(self, interaction: discord.Interaction):
        await reply(interaction, embed=text_only_embed("Shutting down bot..."))
        await self.bot.close()

    @app_commands.command(name="help", description="Displays all bot commands")
    @app_commands.guild_only()
    async def help(self,interaction: discord.Interaction):
        embed = discord.Embed(color=discord.Color.blue())
        embed.set_thumbnail(url=DIS_BOT_THUMBNAIL)
        body_text: list[str] = ["```"]
        for c in self.bot.tree.walk_commands():
            body_text.append(f"{c.name}: {c.description}")
        body_text.append("```")
        embed.add_field(name="Miku commands:",value="\n".join(body_text))
        await reply(interaction, embed=embed,file=gen_bot_thumbnail())
        return None

    @app_commands.command(name="unstuck", description="Use when bot stuck")
    @app_commands.guild_only()
    async def unstuck(self, interaction: discord.Interaction):
        if not (g_id := interaction.guild_id): return None
        miku_cog = self.bot.get_cog("MikuMusicCommands")
        if not isinstance(miku_cog, MikuMusicCommands): return None
        con = await miku_cog.return_gp_con(g_id)
        await con.hard_reset()
        await reply(interaction, embed=text_only_embed("Unstucking bot..."))
        return None

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(utilCommands(bot))
