from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import override

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
from hatsune_miku_bot.cogs.music import MikuMusicCommands
from hatsune_miku_bot.db_logging.db_main import DBLogic
from hatsune_miku_bot.utils.discord_helpers import reply, text_only_embed

logger = logging.getLogger(__name__)


class Bot(commands.Bot):
    def __init__(
        self, owner_id: int | None, db_logic: DBLogic, debugger_on: bool = False
    ) -> None:
        self.synced: bool = False
        self.debugger_on = debugger_on
        self.process_start = datetime.now(UTC)
        self.db_logic = db_logic
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
        logger.info(
            "Bot joined guild %s",
            guild.name,
            extra={
                "event": "bot_guild_joined",
                "guild_id": guild.id,
            },
        )
        try:
            await self.tree.sync(guild=guild)
            logger.info(
                "Synced guild-scoped commands to %s",
                guild.name,
                extra={
                    "event": "guild_commands_synced",
                    "guild_id": guild.id,
                },
            )
        except discord.Forbidden:
            logger.error(
                "Missing permission to sync commands in guild %s",
                guild.name,
                extra={
                    "event": "guild_command_sync_permission_denied",
                    "guild_id": guild.id,
                },
            )
        except discord.HTTPException as e:
            logger.error(
                "HTTP command sync failed in guild %s [status=%s code=%s]",
                guild.name,
                e.status,
                e.code,
                extra={
                    "event": "guild_command_sync_http_failed",
                    "guild_id": guild.id,
                    "exception": str(e),
                },
            )
        except discord.DiscordException:
            logger.exception(
                "Discord command sync failed in guild %s",
                guild.name,
                extra={
                    "event": "guild_command_sync_failed",
                    "guild_id": guild.id,
                },
            )
        except Exception:
            logger.exception(
                "Unexpected command sync failure in guild %s",
                guild.name,
                extra={
                    "event": "guild_command_sync_unexpected_failure",
                    "guild_id": guild.id,
                },
            )

    @override
    async def setup_hook(self) -> None:
        if self.debugger_on:
            if not USER_ID or not GUILD_ID:
                logger.warning(
                    "Debug commands require USER_ID and GUILD_ID",
                    extra={"event": "debug_command_configuration_missing"},
                )
            else:
                await self.load_extension("hatsune_miku_bot.cogs.debug")
        await self.load_extension("hatsune_miku_bot.cogs.utility")
        await self.add_cog(MikuMusicCommands(self, self.db_logic))
        for ext in self.extensions:
            logger.info(
                "Loaded extension %s",
                ext,
                extra={"event": "bot_extension_loaded"},
            )

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
        if self.user:
            for g in self.guilds:
                logger.info(
                    "Logged in as %s on guild %s",
                    self.user,
                    g.name,
                    extra={
                        "event": "bot_guild_session_ready",
                        "guild_id": g.id,
                    },
                )
        if not self.synced:
            for g in self.guilds:
                await self.tree.sync(guild=g)
                logger.info(
                    "Synced guild command set for %s",
                    g.name,
                    extra={
                        "event": "guild_commands_synced",
                        "guild_id": g.id,
                    },
                )
            self.synced = True
        logger.info("Bot is ready", extra={"event": "bot_ready"})
        return None

    async def on_disconnect(self) -> None:
        logger.info(
            "Bot disconnected from Discord",
            extra={"event": "bot_disconnected"},
        )
        return None

    async def on_resumed(self) -> None:
        logger.info(
            "Bot reconnected to Discord",
            extra={"event": "bot_reconnected"},
        )
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
            original_error = getattr(error, "original", error)
            logger.error(
                "Application command failed: %s",
                original_error,
                exc_info=(
                    type(original_error),
                    original_error,
                    original_error.__traceback__,
                ),
                extra={
                    "event": "application_command_failed",
                    "guild_id": getattr(interaction, "guild_id", None),
                    "exception": str(original_error),
                },
            )
            await reply(
                interaction, embed=text_only_embed("Error has occured!")
            )
        return None


def botsetup(db_logic: DBLogic, debugger_on: bool = False) -> tuple[Bot, str]:
    if not DISCORD_TOKEN:
        raise ValueError("Discord token cannot be none")
    return (
        Bot(owner_id=USER_ID, db_logic=db_logic, debugger_on=debugger_on),
        DISCORD_TOKEN,
    )
