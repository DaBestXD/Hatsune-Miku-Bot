import logging
import discord
import discord.utils
import asyncio
from botextras.constants import USER_ID, GUILD_OBJECT
from botextras.bot_funcs_ext import owner_command
from discord.ext import commands
from discord import Interaction, InteractionCallbackResponse, WebhookMessage, app_commands
class botDebugger(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.logger = logging.getLogger(__class__.__name__)

    async def reply(self, interaction: discord.Interaction, msg: str, **kwargs)-> WebhookMessage | InteractionCallbackResponse:
        if interaction.response.is_done():
            return await interaction.followup.send(msg, **kwargs)
        return await interaction.response.send_message(msg, **kwargs)


    @app_commands.command(name="commands", description="List out bot commands")
    @app_commands.guilds(GUILD_OBJECT, discord.Object(id=1476597945540280502))
    @owner_command()
    async def list_commands(self, interaction: Interaction):
        for n in self.bot.cogs.keys():
            bot_cog = self.bot.get_cog(n)
            if bot_cog:
                for c in bot_cog.get_app_commands():
                    print(c)
        await self.reply(interaction, "Commands")
        return None

    @app_commands.command(name="cog_reload", description="Reloads a cog")
    @app_commands.guilds(GUILD_OBJECT, discord.Object(id=1476597945540280502))
    @owner_command()
    async def reload_cog(self, interaction: Interaction, cog_name: str):
        strcog = f"cogs.{cog_name}"
        if strcog in self.bot.extensions:
            await self.bot.reload_extension(strcog)
            await self.bot.tree.sync()
            for g in self.bot.guilds:
                await self.bot.tree.sync(guild=g)
            await self.reply(interaction, f"`Reloading {strcog}`")
        else:
            strsli :list[str] = []
            strsli.append("```\n")
            for n in self.bot.cogs.values():
                strsli.append(f"{n}\n")
            strsli.append("```")
            await self.reply(interaction, "".join(strsli))
        return None

    @app_commands.command(name="die", description="Shuts down bot")
    @app_commands.guilds(GUILD_OBJECT, discord.Object(id=1476597945540280502))
    @owner_command()
    async def die(self, interaction: discord.Interaction) -> None:
        if not USER_ID:
            await self.reply(interaction, "`User ID was never provided`", ephemeral=True)
            return None
        if interaction.user.id == USER_ID:
            await self.reply(interaction, "`Shutting down...`")
            await self.bot.close()
            return None
        await self.reply(interaction, "Not allowed", ephemeral=True)
        return None

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(botDebugger(bot))
