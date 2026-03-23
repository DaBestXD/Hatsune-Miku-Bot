from __future__ import annotations
import discord
from botextras.constants import USER_ID
from botextras.config import ASSET_DIR
from discord import (Color, Interaction, WebhookMessage,
    InteractionCallbackResponse,app_commands)

def owner_command():
    async def predicate(interaction: Interaction)-> bool:
        return interaction.user.id == USER_ID
    return app_commands.check(predicate)

async def reply(interaction: discord.Interaction, msg: str = "", **kwargs)-> WebhookMessage|InteractionCallbackResponse|None:
    try:
        if interaction.response.is_done():
            return await interaction.followup.send(msg, **kwargs)
        return await interaction.response.send_message(msg, **kwargs)
    except discord.NotFound:
        return None


def text_only_embed(txt: str) -> discord.Embed:
    embed = discord.Embed(color=Color.blue())
    embed.set_author(name=txt)
    return embed

def gen_bot_thumbnail() -> discord.File:
    img_path = ASSET_DIR / "hatsuneplush.jpg"
    bot_thumbnail = discord.File(img_path, filename="hatsuneplush.jpg")
    return bot_thumbnail

def code_block_embed(txt: list[str],title: str) -> discord.Embed:
    body_txt: list[str] = ["```"]
    body_txt.extend(txt)
    body_txt.append("```")
    embed = discord.Embed(color=discord.Color.blue())
    embed.add_field(name=title,value="\n".join(body_txt))
    return embed
