import os
import discord
from dotenv import load_dotenv
from botextras.loadenv_values import load_env_vals

load_env_vals()
load_dotenv()
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
GUILD_OBJECT = discord.Object(id=GUILD_ID)
USER_ID = int(os.getenv("USER_ID"))
