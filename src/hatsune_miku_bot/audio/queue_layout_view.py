from __future__ import annotations

from typing import TYPE_CHECKING, cast, override

from discord import (
    ButtonStyle,
    Color,
    Interaction,
    InteractionMessage,
    SeparatorSpacing,
)
from discord.ui import (
    ActionRow,
    Button,
    Container,
    LayoutView,
    Section,
    Separator,
    TextDisplay,
    Thumbnail,
)

from hatsune_miku_bot.audio.song_playlist_classes import Song
from hatsune_miku_bot.bot_config.constants import DIS_BOT_THUMBNAIL

if TYPE_CHECKING:
    from hatsune_miku_bot.cogs.music import MikuMusicCommands


class QueueLayoutView(LayoutView):
    def __init__(
        self,
        music_cog: MikuMusicCommands,
        id: int,
    ) -> None:
        # NOTE: this type will be always be set unless something
        # truly terrible has occured, this is just being set to none
        # to create the attribute
        self.message: InteractionMessage = None  # type: ignore
        super().__init__(timeout=90)
        self.add_item(QueueContainer(music_cog, id))

    @override
    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, Button):
                item.disabled = True
        await self.message.edit(view=self)
        return None


class QueueContainer(Container[QueueLayoutView]):
    def __init__(
        self,
        music_cog: MikuMusicCommands,
        id: int,
    ) -> None:
        self.music_cog = music_cog
        self.music_controller = music_cog.guildstate_con_dict[id]
        self._header_text = TextDisplay(
            content=f" **Currently Playing:**\n## [{self.song_queue[0].title}]({self.song_queue[0].webpage_url})\n"  # noqa: E501
            f"-# Duration • {self.current_song.formatted_duration}"
        )
        self.header = Section[QueueLayoutView](
            self._header_text,
            accessory=Thumbnail(media=DIS_BOT_THUMBNAIL),
        )
        self.playlist_body = TextDisplay[QueueLayoutView](
            content=self.pretty_print_10_songs(page_num=0)
        )

        # NOTE: Buttons for queue container
        self.page_left = QueuePageLeftButton(disabled=self.queue_length < 2)
        self.page_right = QueuePageRightButton(disabled=self.queue_length < 11)
        self.shuffle_button = QueueShuffleButton(disabled=self.queue_length < 2)
        self.nightcore_button = QueueNightcoreButton()
        self.stop_button = QueueStopButton()
        self.max_song_per_page = 10
        self.page_number: int = 0
        super().__init__(
            # Header section
            self.header,
            Separator(spacing=SeparatorSpacing.large),
            # Playlist body
            self.playlist_body,
            # Queue controls
            Separator(spacing=SeparatorSpacing.large),
            ActionRow[QueueLayoutView](
                self.page_left,
                self.page_right,
                self.shuffle_button,
                self.nightcore_button,
                self.stop_button,
            ),
            accent_color=Color.blue(),
        )

    def get_current_page(self) -> int:
        return 0

    @property
    def queue_length(self) -> int:
        return len(self.music_controller.state.songs)

    @property
    def song_queue(self) -> list[Song]:
        return self.music_controller.state.songs

    @property
    def current_song(self) -> Song:
        return self.music_controller.state.songs[0]

    @property
    def max_pages(self) -> int:
        return len(self.music_controller.state.songs) // self.max_song_per_page

    def pretty_print_10_songs(self, *, page_num: int) -> str:
        if page_num == 0:
            # Page 0 special case where you skip the first song in the queue
            # as thats the currently playing song.
            playlist_slice = slice(1, 11)
        else:
            end = page_num * self.max_song_per_page
            start = end - self.max_song_per_page
            playlist_slice = slice(start, end)
        content_body = "\n".join(
            (
                f"{i}. [{s.safe_title()}]({s.webpage_url}) • `{s.formatted_duration}`"  # noqa: E501
                for i, s in enumerate(self.song_queue[playlist_slice])
            )
        )
        return content_body if content_body else "Queue Empty!"

    def next_page(self) -> None:
        pass

    def previous_page(self) -> None:
        pass

    def set_header_text(self) -> None:
        # fmt: off
        self._header_text.content = (
            f"Currently Playing: {self.current_song.safe_title(max_length=30)}\n" # noqa: E501
            f"-# Duration: {self.current_song.formatted_duration}"
        )
        # fmt: on

    def set_body_text(self) -> None:
        self.playlist_body.content = self.pretty_print_10_songs(
            page_num=self.page_number
        )

    def set_total_layout_view(self) -> None:
        return


# NOTE: I HATE INHERITANCE THIS IS RETARDED BUT WHATEVER
# TO MAKE IT WORK IM SURE THERES SOME TYPE ANNOTATION MAGIC
# TO AVOID THIS DISASTER


class QueuePageLeftButton(Button[QueueLayoutView]):
    def __init__(self, *, disabled: bool) -> None:
        super().__init__(
            emoji="⬅️", style=ButtonStyle.secondary, disabled=disabled
        )

    @override
    async def callback(self, interaction: Interaction) -> None:
        pass


class QueuePageRightButton(Button[QueueLayoutView]):
    def __init__(self, *, disabled: bool) -> None:
        super().__init__(
            emoji="➡️", style=ButtonStyle.secondary, disabled=disabled
        )

    @override
    async def callback(self, interaction: Interaction) -> None:
        assert interaction.guild_id and self.parent
        assert self.view
        container = cast(QueueContainer, self.parent.parent)
        cog_queue = container.music_cog.guildstate_con_dict[
            interaction.guild_id
        ]
        assert cog_queue
        container.page_number += 1


class QueueShuffleButton(Button[QueueLayoutView]):
    def __init__(self, *, disabled: bool) -> None:
        super().__init__(
            emoji="🔀", style=ButtonStyle.secondary, disabled=disabled
        )

    @override
    async def callback(self, interaction: Interaction) -> None:
        assert interaction.guild_id and self.parent and self.view
        container = cast(QueueContainer, self.parent.parent)
        cog_queue = container.music_cog.guildstate_con_dict[
            interaction.guild_id
        ]
        await cog_queue.add_event(cog_queue.shuffle, interaction)
        container.set_body_text()
        await self.view.message.edit(view=self.view)


class QueueStopButton(Button[QueueLayoutView]):
    def __init__(self) -> None:
        super().__init__(label="STOP", style=ButtonStyle.success)

    @override
    async def callback(self, interaction: Interaction) -> None:
        assert interaction.guild_id and self.parent and self.view
        container = cast(QueueContainer, self.parent.parent)
        cog_queue = container.music_cog.guildstate_con_dict[
            interaction.guild_id
        ]
        await cog_queue.add_event(cog_queue.stop_playback, interaction)
        await self.view.message.edit(view=self.view)


class QueueNightcoreButton(Button[QueueLayoutView]):
    def __init__(self) -> None:
        super().__init__(
            # NOTE: change this to <:WAPPLE:883418567654117426> in prod
            emoji="🍎",
            style=ButtonStyle.danger,
        )

    @override
    async def callback(self, interaction: Interaction) -> None:
        assert interaction.guild_id and self.parent and self.view
        container = cast(QueueContainer, self.parent.parent)
        cog_queue = container.music_cog.guildstate_con_dict[
            interaction.guild_id
        ]
        await self.view.on_timeout()
        await cog_queue.add_event(cog_queue.nightcore, interaction)
        await self.view.message.edit(view=self.view)
