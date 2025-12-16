import discord
import os
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')  
guild_id = 1409781190545772614
guild = discord.Object(id=1409781190545772614)
class Bot(commands.Bot):
    async def setup_hook(self)->None:
        await self.load_extension("cogs.musicplayer")
        bot.tree.remove_command('test')
        await self.tree.sync(guild=guild)
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = Bot(command_prefix='!',intents=intents)
@bot.event
async def on_ready()->None:
    print(f'Logged in as {bot.user} on {bot.get_guild(guild_id)}')
    commands = await bot.tree.fetch_commands(guild=guild)
    names = [name.name for name in commands]
    print(f'{names}')
bot.run(DISCORD_TOKEN)


