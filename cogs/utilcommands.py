import discord
from discord import app_commands
from discord.ext import commands
from botextras.bot_funcs_ext import owner_command,reply,txt_only_embed

class utilCommands(commands.Cog):
    """
    Bot util commands
    Cogname: utilcommands
    """
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="die", description="Turns off bot")
    @owner_command()
    async def die(self, interaction: discord.Interaction):
        await reply(interaction, embed=txt_only_embed("Shutting down bot..."))
        await self.bot.close()

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(utilCommands(bot))
