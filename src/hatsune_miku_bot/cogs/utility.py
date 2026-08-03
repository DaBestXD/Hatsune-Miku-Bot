import asyncio
import tempfile
from typing import cast

import discord
from discord import Interaction, InteractionResponse, app_commands
from discord.ext import commands
from yt_dlp.utils import DownloadError

from hatsune_miku_bot.audio.audio_resolver import generic_download_logic
from hatsune_miku_bot.bot_config.constants import (
    DIS_BOT_THUMBNAIL,
    GUILD_OBJECT,
)
from hatsune_miku_bot.utils.discord_helpers import (
    gen_bot_thumbnail,
    owner_command,
    reply,
    text_only_embed,
)

if not GUILD_OBJECT:
    raise RuntimeError("Guild object cannot be none")


class UtilityCommands(commands.Cog):
    """
    Bot util commands
    Cogname: UtilityCommands
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.download_lock = asyncio.Lock()

    @app_commands.command(name="die", description="Turns off bot")
    @app_commands.guild_only()
    @owner_command()
    async def die(self, interaction: Interaction):
        await reply(interaction, embed=text_only_embed("Shutting down bot..."))
        await self.bot.close()

    @app_commands.command(name="help", description="Displays all bot commands")
    @app_commands.guild_only()
    async def help(self, interaction: Interaction):
        embed = discord.Embed(color=discord.Color.blue())
        embed.set_thumbnail(url=DIS_BOT_THUMBNAIL)
        body_text: list[str] = ["```"]
        for c in self.bot.tree.walk_commands():
            body_text.append(f"{c.name}: {c.description}")
        body_text.append("```")
        embed.add_field(name="Miku commands:", value="\n".join(body_text))
        await reply(interaction, embed=embed, file=gen_bot_thumbnail())
        return None

    @app_commands.command(
        name="download-any", description="easy to use yt_dlp downloader"
    )
    @app_commands.describe(audio_only="Use for an audio only download")
    @app_commands.guild_only()
    async def download_any(
        self, interaction: Interaction, url: str, audio_only: bool = False
    ) -> None:
        # WARNING: DANGEROUS COMMAND MAYBE ADD ROLE RESTRICTION LATER
        response = cast(InteractionResponse, interaction.response)
        if self.download_lock.locked():
            await reply(
                interaction,
                embed=text_only_embed(
                    "Download already in progress please wait"
                ),
            )
            return None
        await response.defer()
        try:
            async with self.download_lock:
                with tempfile.TemporaryDirectory(
                    ignore_cleanup_errors=True
                ) as tmp_dir:
                    file = await asyncio.to_thread(
                        generic_download_logic, url, tmp_dir, audio_only
                    )
                    await reply(interaction, file=file)
        except ValueError:
            await reply(
                interaction,
                embed=text_only_embed("File size was over 10mb file limit"),
            )
            return None
        except DownloadError:
            await reply(
                interaction,
                embed=text_only_embed(
                    "Something went wrong try a different link!"
                ),
            )
            return None


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UtilityCommands(bot))
