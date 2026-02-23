import discord
from discord.ext import commands
from botextras.constants import DISCORD_TOKEN, GUILD_ID, GUILD_OBJECT


def main():
    if not DISCORD_TOKEN:
        raise KeyError("Discord Token cannot be none")
    if not GUILD_ID:
        raise KeyError("Guild ID cannot be none")

    class Bot(commands.Bot):
        async def setup_hook(self) -> None:
            await self.load_extension("cogs.musicplayer")
            await self.tree.sync(guild=GUILD_OBJECT)

    intents = discord.Intents.default()
    intents.message_content = True
    intents.voice_states = True
    bot = Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready() -> None:
        print(f"Logged in as {bot.user} on {bot.get_guild(int(GUILD_ID))}")

    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
