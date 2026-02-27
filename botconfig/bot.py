import logging
import discord
from discord.app_commands import CheckFailure
from discord.app_commands.errors import AppCommandError
from discord.ext import commands
from discord.interactions import Interaction
from botextras.constants import USER_ID, DISCORD_TOKEN
from botextras.bot_funcs_ext import reply

class Bot(commands.Bot):
    def __init__(self, owner_id: int|None) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.synced: bool = False
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix="!", intents=intents, owner_id=owner_id)

    async def on_guild_join(self, guild: discord.Guild) -> None:
        self.logger.info("Joined: %s", guild.name)
        try:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            self.logger.info("Synced commands to: %s[%d]", guild.name, guild.id)
        except discord.Forbidden:
            self.logger.warning("No permission to sync in guild %s, (%d)", guild.name, guild.id)
        except discord.HTTPException as e:
            self.logger.error("HTTP sync failure guild: %s, (%d) [status=%s code=%s]", guild.name, guild.id, e.status, e.code)
        except discord.DiscordException:
            self.logger.exception("Discord sync error guild: %s, (%d)", guild.name, guild.id)
        except Exception:
            self.logger.exception("Unexpected sync error guild: %s, (%d)", guild.name, guild.id)

    async def setup_hook(self) -> None:
        # await self.load_extension("cogs.musicplayer")
        await self.load_extension("cogs.debugger")
        await self.load_extension("cogs.rewrite")
        for ext in self.extensions:
            self.logger.info("Loaded %s", ext)
        self.tree.on_error = self.on_app_command_error

    async def on_ready(self) -> None:
        if self.user:
            for g in self.guilds:
                self.logger.info("Logged in as %s on %s[%d]", self.user, g.name, g.id)
        if not self.synced:
            # await self.tree.sync()
            # For remove all guild specific syncs for prod
            for g in self.guilds:
                await self.tree.sync(guild=g)
                self.logger.info("Syncing commands to %s[%d]", g.name, g.id)
            self.synced = True
        return None

    async def on_app_command_error(self, interaction: Interaction, error: AppCommandError) -> None:
        if isinstance(error, CheckFailure):
            await reply(interaction, "Invalid permission: Must be owner of the bot!", ephemeral=True)
        else:
            await reply(interaction, f"{error}")
            self.logger.warning("%s", error)
        return None

def botsetup()-> tuple[Bot, str]:
    assert DISCORD_TOKEN, "Discord token cannot be none"
    return (Bot(owner_id=USER_ID), DISCORD_TOKEN)
