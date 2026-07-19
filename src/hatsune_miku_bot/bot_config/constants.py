from __future__ import annotations

import os

import discord
from dotenv import load_dotenv

from hatsune_miku_bot.bot_config.paths import ENV_PATH, PROJECT_ROOT

load_dotenv(dotenv_path=ENV_PATH)
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
USER_ID = os.getenv("USER_ID")
USER_ID = None if not USER_ID else int(USER_ID)
GUILD_OBJECT = discord.Object(id=int(GUILD_ID)) if GUILD_ID else None
DB_PATH = PROJECT_ROOT / "data" / "status.db"
INVIS_CHAR = "\u200b"
DIS_BOT_THUMBNAIL = "attachment://hatsuneplush.jpg"
