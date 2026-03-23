from __future__ import annotations
import logging
import discord
from discord import Interaction
from discord.app_commands import CheckFailure
from discord.app_commands.errors import AppCommandError
from discord.ext import commands
from botextras.constants import GUILD_ID, USER_ID, DISCORD_TOKEN
from botextras.bot_funcs_ext import reply, text_only_embed
from db_stuff.db_logic import insert_event, utc_now_dt
from datetime import datetime, timezone

class Bot(commands.Bot):
    def __init__(self, owner_id: int|None, debugger_on: bool = False) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.synced: bool = False
        self.debugger_on = debugger_on
        self.process_start = datetime.now(timezone.utc)
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix="!", intents=intents, owner_id=owner_id, help_command=None)

    async def on_guild_join(self, guild: discord.Guild) -> None:
        self.logger.info("Joined: %s", guild.name)
        try:
            await self.tree.sync(guild=guild)
            self.logger.info("Synced guild-scoped commands to: %s[%d]", guild.name, guild.id)
        except discord.Forbidden:
            self.logger.error("No permission to sync in guild %s, (%d)", guild.name, guild.id)
        except discord.HTTPException as e:
            self.logger.error("HTTP sync failure guild: %s, (%d) [status=%s code=%s]", guild.name, guild.id, e.status, e.code)
        except discord.DiscordException:
            self.logger.error("Discord sync error guild: %s, (%d)", guild.name, guild.id)
        except Exception:
            self.logger.error("Unexpected sync error guild: %s, (%d)", guild.name, guild.id)

    async def setup_hook(self) -> None:
        await self.load_extension("cogs.musicplayer")
        if self.debugger_on and USER_ID and GUILD_ID:
            await self.load_extension("cogs.debugger")
        await self.load_extension("cogs.utilcommands")
        for ext in self.extensions:
            self.logger.info("Loaded %s", ext)
        self.tree.on_error = self.on_app_command_error
        await self.tree.sync()

    async def on_resumed(self) -> None:
        self.discord_connected = True
        await insert_event("bot_resume",utc_now_dt().isoformat(),"Bot has resumed")


    async def on_ready(self) -> None:
        self.discord_connected = True
        if self.user:
            for g in self.guilds:
                self.logger.info("Logged in as %s on %s[%d]", self.user, g.name, g.id)
                await insert_event("bot_ready",utc_now_dt().isoformat(), f"Bot logged into {g.name}[{g.id}]")
        if not self.synced:
            for g in self.guilds:
                await self.tree.sync(guild=g)
                self.logger.info("Synced guild command set for %s[%d]", g.name, g.id)
            self.synced = True
        self.logger.info("Ready to go!😼")
        return None

    async def on_disconnect(self) -> None:
        self.discord_connected = False
        await insert_event("discord_disconnect",utc_now_dt().isoformat(), "Bot has disconnected")

    async def on_app_command_error(self, interaction: Interaction, error: AppCommandError) -> None:
        if isinstance(error, CheckFailure):
            await reply(interaction, "Invalid permission: Must be owner of the bot!", ephemeral=True)
        else:
            await reply(interaction, embed=text_only_embed("Error has occured!"))
            await insert_event("app_command_error",utc_now_dt().isoformat(),str(error))
            self.logger.warning("%s", error)
        return None

def botsetup(debugger_on:bool = False)-> tuple[Bot, str]:
    assert DISCORD_TOKEN, "Discord token cannot be none"
    return (Bot(owner_id=USER_ID,debugger_on=debugger_on), DISCORD_TOKEN)
