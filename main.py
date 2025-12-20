import discord
import os
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')  
GUILD_ID = os.getenv('SERVER_ID')
guild = discord.Object(id=GUILD_ID)
class Bot(commands.Bot):
    async def setup_hook(self)->None:
        await self.load_extension("cogs.musicplayer")
        #await self.load_extension("cogs.commandsync")
        await self.tree.sync(guild=guild)
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = Bot(command_prefix='!',intents=intents)
@bot.event
async def on_ready()->None:
    print(f'Logged in as {bot.user} on {bot.get_guild(int(GUILD_ID))}')
    #commands = await bot.tree.fetch_commands(guild=guild)
bot.run(DISCORD_TOKEN)


