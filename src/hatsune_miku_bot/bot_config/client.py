from __future__ import annotations

import logging
from datetime import UTC, datetime

import discord
from discord import Interaction
from discord.app_commands import CheckFailure
from discord.app_commands.errors import AppCommandError
from discord.ext import commands

from hatsune_miku_bot.bot_config.constants import (
    DISCORD_TOKEN,
    GUILD_ID,
    USER_ID,
)
from hatsune_miku_bot.utils.discord_helpers import reply, text_only_embed

logger = logging.getLogger(__name__)


class Bot(commands.Bot):
    def __init__(self, owner_id: int | None, debugger_on: bool = False) -> None:
        self.synced: bool = False
        self.debugger_on = debugger_on
        self.process_start = datetime.now(UTC)
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        super().__init__(
            command_prefix="!",
            intents=intents,
            owner_id=owner_id,
            help_command=None,
        )

    async def on_guild_join(self, guild: discord.Guild) -> None:
        logger.info("Joined: %s", guild.name)
        try:
            await self.tree.sync(guild=guild)
            logger.info(
                "Synced guild-scoped commands to: %s[%d]", guild.name, guild.id
            )
        except discord.Forbidden:
            logger.error(
                "No permission to sync in guild %s, (%d)", guild.name, guild.id
            )
        except discord.HTTPException as e:
            logger.error(
                "HTTP sync failure guild: %s, (%d) [status=%s code=%s]",
                guild.name,
                guild.id,
                e.status,
                e.code,
            )
        except discord.DiscordException:
            logger.error(
                "Discord sync error guild: %s, (%d)", guild.name, guild.id
            )
        except Exception:
            logger.error(
                "Unexpected sync error guild: %s, (%d)", guild.name, guild.id
            )

    async def setup_hook(self) -> None:
        await self.load_extension("hatsune_miku_bot.cogs.music")
        if self.debugger_on:
            if not USER_ID or not GUILD_ID:
                logger.warning(
                    "Enabled debugger without user_id or guild_id will not load debugging commands"  # noqa: E501
                )
            else:
                await self.load_extension("hatsune_miku_bot.cogs.debug")
        await self.load_extension("hatsune_miku_bot.cogs.utility")
        for ext in self.extensions:
            logger.info("Loaded %s", ext)

        @self.tree.error
        async def handle_app_command_error(
            interaction: Interaction,
            error: AppCommandError,
            /,
        ) -> None:
            await self.on_app_command_error(interaction, error)
            return None

        await self.tree.sync()
        return None

    async def on_ready(self) -> None:
        self.discord_connected = True
        if self.user:
            for g in self.guilds:
                logger.info(
                    "Logged in as %s on %s[%d]", self.user, g.name, g.id
                )
        if not self.synced:
            for g in self.guilds:
                await self.tree.sync(guild=g)
                logger.info("Synced guild command set for %s[%d]", g.name, g.id)
            self.synced = True
        logger.info("Ready to go!😼")
        return None

    async def on_disconnect(self) -> None:
        logger.info("Bot has disconnected")
        return None

    async def on_app_command_error(
        self, interaction: Interaction, error: AppCommandError, /
    ) -> None:
        if isinstance(error, CheckFailure):
            await reply(
                interaction,
                "Invalid permission: Must be owner of the bot!",
                ephemeral=True,
            )
        else:
            await reply(
                interaction, embed=text_only_embed("Error has occured!")
            )
            logger.error("%s", error)
        return None


def botsetup(debugger_on: bool = False) -> tuple[Bot, str]:
    if not DISCORD_TOKEN:
        raise ValueError("Discord token cannot be none")
    return (Bot(owner_id=USER_ID, debugger_on=debugger_on), DISCORD_TOKEN)
