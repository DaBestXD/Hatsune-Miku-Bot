import discord
from discord import app_commands
from discord.ext import commands

from hatsune_miku_bot.bot_config.constants import DIS_BOT_THUMBNAIL
from hatsune_miku_bot.utils.discord_helpers import (
    gen_bot_thumbnail,
    owner_command,
    reply,
    text_only_embed,
)


class UtilityCommands(commands.Cog):
    """
    Bot util commands
    Cogname: UtilityCommands
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
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(color=discord.Color.blue())
        embed.set_thumbnail(url=DIS_BOT_THUMBNAIL)
        body_text: list[str] = ["```"]
        for c in self.bot.tree.walk_commands():
            body_text.append(f"{c.name}: {c.description}")
        body_text.append("```")
        embed.add_field(name="Miku commands:", value="\n".join(body_text))
        await reply(interaction, embed=embed, file=gen_bot_thumbnail())
        return None


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UtilityCommands(bot))
