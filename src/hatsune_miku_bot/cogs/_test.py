from __future__ import annotations

from collections.abc import Generator
from typing import override

from discord import (
    Color,
    Interaction,
    InteractionMessage,
    SelectOption,
    SeparatorSpacing,
    app_commands,
)
from discord.ext import commands
from discord.ui import (
    ActionRow,
    Button,
    Container,
    LayoutView,
    Section,
    Select,
    Separator,
    TextDisplay,
    Thumbnail,
)
from discord.ui.select import BaseSelect

from hatsune_miku_bot.audio.song_playlist_classes import Song
from hatsune_miku_bot.bot_config.constants import GUILD_OBJECT, INVIS_CHAR
from hatsune_miku_bot.db_logging.db_main import DBLogic
from hatsune_miku_bot.utils.discord_helpers import gen_bot_thumbnail, reply

if not GUILD_OBJECT:
    raise RuntimeError("Guild object cannot be none")


class MainCustomPlaylistLV(LayoutView):
    def __init__(
        self,
        init_options: list[str],
    ) -> None:
        super().__init__(timeout=180)
        self.main_container = CustomPlaylistContainer(init_options, 1)
        self.add_item(self.main_container)
        self.message: InteractionMessage | None = None

    async def on_timeout(self) -> None:
        self.main_container.header_text.content = (
            "# Playlist Controller expired!"
        )
        # TODO: change this before deploying
        self.main_container.selection_text.content = (
            "### Use /Place-Holder-Command-Name again!"
        )
        for i in self.walk_children():
            if isinstance(i, (Button, BaseSelect)):
                i.disabled = True
        # NOTE: self.message will always be set
        assert self.message
        await self.message.edit(view=self)


class CustomPlaylistContainer(Container[MainCustomPlaylistLV]):
    def __init__(self, init_playlist_names: list[str], guild_id: int) -> None:
        self.header_text = TextDisplay(content="# Custom Playlist Controller")
        self.header_section = Section(
            TextDisplay(content=INVIS_CHAR),
            self.header_text,
            accessory=Thumbnail(gen_bot_thumbnail()),
        )
        self.playlist_selector = PlaylistSelection(
            init_playlist_names, guild_id
        )
        self.act_playlist_selector = ActionRow(self.playlist_selector)
        self.selection_text = TextDisplay(
            content="###  Pick a playlist to perform actions on!",
        )
        self.playlist_paginator = PlaylistPaginator(
            init_playlist_names, guild_id
        )
        super().__init__(
            self.header_section,
            Separator(spacing=SeparatorSpacing.large),
            self.selection_text,
            self.act_playlist_selector,
            self.playlist_paginator,
            accent_color=Color.blue(),
        )

    def _convert_str_list_to_options(
        self, options: list[str]
    ) -> Generator[SelectOption]:
        return (SelectOption(label=o) for o in options)

    async def edit_selection_options(self, options: list[str]) -> None:
        self.playlist_selector.options = list(
            self._convert_str_list_to_options(options)
        )


class PlaylistSelection(Select[MainCustomPlaylistLV]):
    def __init__(
        self,
        playlist_names: list[str],
        guild_id: int,
    ) -> None:
        self.selection_options: list[SelectOption] = [
            SelectOption(label=p) for p in playlist_names[:25]
        ]
        self.guild_id = guild_id
        super().__init__(options=self.selection_options)

    @override
    async def callback(self, interaction: Interaction):
        await interaction.response.defer()
        # NOTE: Multiple asserts are used for conditions that can never happen
        # and are for the type checker to not complain
        assert self.view is not None
        selected = self.values[0]
        self.view.main_container.selection_text.content = (
            f" ### Currently selected: {selected}"
        )
        await interaction.edit_original_response(view=self.view)


class PlaylistPaginator(ActionRow[MainCustomPlaylistLV]):
    def __init__(self, init_playlist_names: list[str], guild_id: int) -> None:
        self.page_left_button = PageLeftButton(start_disabled=True)
        right_enabled = len(init_playlist_names) > 25
        self.page_right_button = PageRightButton(start_disabled=right_enabled)
        self.playlist_current_page = 0
        self.songs_current_page = 0
        self.playlist_mode: bool = True
        super().__init__(
            self.page_left_button,
            self.page_right_button,
        )


class PageRightButton(Button[MainCustomPlaylistLV]):
    def __init__(self, *, start_disabled: bool) -> None:
        super().__init__(emoji="➡️", disabled=start_disabled)

    @override
    async def callback(self, interaction: Interaction) -> None:
        assert isinstance(self.parent, PlaylistPaginator)
        if self.parent.playlist_mode:
            self.parent.playlist_current_page += 1
        else:
            self.parent.songs_current_page += 1
        await reply(interaction, content=f"Hello from {self}")


class PageLeftButton(Button[MainCustomPlaylistLV]):
    def __init__(self, start_disabled: bool) -> None:
        super().__init__(emoji="⬅️", disabled=start_disabled)

    @override
    async def callback(self, interaction: Interaction) -> None:
        await reply(interaction, content=f"Hello from {self}")


class Test_cog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def return_playlist_names(
        self, interaction: Interaction
    ) -> list[str]:
        return await self.db.fetch_playlist_names(interaction)

    async def get_playlist_items(
        self, interaction: Interaction, playlist_name: str
    ) -> list[Song]:
        return await self.db.get_playlist_songs(interaction, playlist_name)

    @override
    async def cog_load(self) -> None:
        print("loaded db")
        self.db = await DBLogic.async_init()

    @override
    async def cog_unload(self) -> None:
        print("unloaded db")
        await self.db.close()

    @app_commands.command(name="test-queue-view")
    @app_commands.guilds(GUILD_OBJECT)
    async def test_queue_view(self, interaction: Interaction):
        # names = await self.return_playlist_names(interaction)
        names = [f"Playlist {i}" for i in range(100)]
        custom_view = MainCustomPlaylistLV(names)
        await reply(interaction, view=custom_view, file=gen_bot_thumbnail())
        custom_view.message = await interaction.original_response()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Test_cog(bot))
