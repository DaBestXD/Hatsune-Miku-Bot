from __future__ import annotations
import discord
from botextras.constants import USER_ID, ASSET_DIR
from discord import (Color, Interaction, WebhookMessage,
    InteractionCallbackResponse,app_commands)

def owner_command():
    async def predicate(interaction: Interaction)-> bool:
        return interaction.user.id == USER_ID
    return app_commands.check(predicate)

async def reply(interaction: discord.Interaction, msg: str = "", **kwargs)-> WebhookMessage | InteractionCallbackResponse:
    if interaction.response.is_done():
        return await interaction.followup.send(msg, **kwargs)
    return await interaction.response.send_message(msg, **kwargs)


def txt_only_embed(txt: str) -> discord.Embed:
    embed = discord.Embed(color=Color.blue())
    embed.set_author(name=txt)
    return embed

def gen_bot_thumbnail() -> discord.File:
    img_path = ASSET_DIR / "hatsuneplush.jpg"
    bot_thumbnail = discord.File(img_path, filename="hatsuneplush.jpg")
    return bot_thumbnail
