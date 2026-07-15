from __future__ import annotations

from typing import TypedDict, Unpack

import discord
from discord import (
    Color,
    Interaction,
    InteractionCallbackResponse,
    WebhookMessage,
    app_commands,
)

from hatsune_miku_bot.bot_config.constants import USER_ID
from hatsune_miku_bot.bot_config.paths import ASSET_DIR


class _ReplyDict(TypedDict, total=False):
    embed: discord.Embed
    file: discord.File
    ephemeral: bool


def owner_command():
    async def predicate(interaction: Interaction) -> bool:
        return interaction.user.id == USER_ID

    return app_commands.check(predicate)


async def reply(
    interaction: discord.Interaction,
    msg: str = "",
    **kwargs: Unpack[_ReplyDict],
) -> WebhookMessage | InteractionCallbackResponse | None:
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


def code_block_embed(txt: list[str], title: str) -> discord.Embed:
    body_txt: list[str] = ["```"]
    body_txt.extend(txt)
    body_txt.append("```")
    embed = discord.Embed(color=discord.Color.blue())
    embed.add_field(name=title, value="\n".join(body_txt))
    return embed
