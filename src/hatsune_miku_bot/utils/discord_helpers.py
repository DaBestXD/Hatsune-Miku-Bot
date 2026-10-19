from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import (
    TypedDict,
    Unpack,
)
from urllib.parse import urlparse

from discord import (
    AllowedMentions,
    Color,
    Embed,
    File,
    Interaction,
    InteractionCallbackResponse,
    NotFound,
    Poll,
    WebhookMessage,
    app_commands,
)
from discord.ui import View

from hatsune_miku_bot.bot_config.constants import USER_ID
from hatsune_miku_bot.bot_config.paths import ASSET_DIR


class ReplyKwargs(TypedDict, total=False):
    allowed_mentions: AllowedMentions
    file: File
    files: Sequence[File]
    ephemeral: bool
    silent: bool
    suppress_embeds: bool
    view: View
    tts: bool
    embed: Embed
    embeds: Sequence[Embed]
    poll: Poll


async def reply(
    interaction: Interaction,
    content: str | None = None,
    **kwargs: Unpack[ReplyKwargs],
) -> WebhookMessage | InteractionCallbackResponse | None:
    try:
        if interaction.response.is_done():
            if content is not None:
                return await interaction.followup.send(content, **kwargs)
            return await interaction.followup.send(**kwargs)
        if content is not None:
            return await interaction.response.send_message(content, **kwargs)
        return await interaction.response.send_message(**kwargs)
    except NotFound:
        return None


def owner_command[T]() -> Callable[[T], T]:
    async def predicate(interaction: Interaction) -> bool:
        return interaction.user.id == USER_ID

    return app_commands.check(predicate)


def text_only_embed(txt: str) -> Embed:
    embed = Embed(color=Color.blue())
    embed.set_author(name=txt)
    return embed


def gen_bot_thumbnail() -> File:
    img_path = ASSET_DIR / "hatsuneplush.jpg"
    bot_thumbnail = File(img_path, filename="hatsuneplush.jpg")
    return bot_thumbnail


def code_block_embed(txt: list[str], title: str) -> Embed:
    body_txt: list[str] = ["```"]
    body_txt.extend(txt)
    body_txt.append("```")
    embed = Embed(color=Color.blue())
    embed.add_field(name=title, value="\n".join(body_txt))
    return embed


def _is_http_url(value: str | None) -> bool:
    if not value:
        return False
    try:
        parsed_url = urlparse(value)
    except ValueError:
        return False
    return parsed_url.scheme.casefold() in {"http", "https"} and bool(
        parsed_url.netloc
    )
