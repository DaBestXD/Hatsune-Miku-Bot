from __future__ import annotations
import discord
from typing import Optional, TYPE_CHECKING
from discord import Color, Interaction, ui
from audio_utils.audio_class import Playlist
from botextras.constants import DIS_BOT_THUMBNAIL, INVIS_CHAR

if TYPE_CHECKING:
    from cogs.musicplayer import MikuMusicCommands
class QueueEmbed():
    def __init__(self, playlist: Playlist, song_loop: bool, night_core: bool) -> None:
        self.playlist = playlist
        self.page_number = 0
        self.max_pages = len(self.playlist.songs) // 10
        self.song_loop: bool = song_loop
        self.night_core: bool = night_core
        self.embed: discord.Embed|None = None
        self.update_embed(playlist)

    def update_embed(self, playlist: Playlist):
        active_song = playlist.songs[0]
        truncated_title:str = active_song.title[:30]
        if len(truncated_title) >= 30: truncated_title += "..."
        truncated_title += f" ({active_song.formatted_duration})"
        if not self.embed:
            self.embed = discord.Embed(title=truncated_title,url=active_song.webpage_url,color=Color.blue())
            self.embed.set_thumbnail(url=DIS_BOT_THUMBNAIL)
            self.embed.set_author(name="Currently playing:")
        else:
            self.embed.title = truncated_title
            self.embed.url = active_song.webpage_url
            self.embed.clear_fields()
        start = self.page_number * 10
        page_slice = slice(start, start+10) if self.page_number >= 1 else slice(1,10)
        body_text: list[str] = []
        if len(playlist.songs) > 1:
            for idx,s in enumerate(playlist.songs[page_slice]):
                safe_title = s.title.replace("[","【").replace("]","】")[:30]
                if len(safe_title) >= 30: safe_title += "..."
                body_text.append(f"{idx+(self.page_number*10)}. [{safe_title}]({s.webpage_url}) `{s.formatted_duration}`")
            self.embed.add_field(name="Song queue:",value="\n".join(body_text),inline=False)
        else:
            self.embed.add_field(name="Song queue:",value="Queue empty!",inline=False)
        human_night = "Enabled" if self.night_core else "Disabled"
        human_loop = "Enabled" if self.song_loop else "Disabled"
        self.embed.add_field(name=f"Queue details:",value=f"Looping:`{human_loop}`\nDuration:`{self.playlist.formatted_duration}`")
        self.embed.add_field(name=INVIS_CHAR,value=f"Nightcore:`{human_night}`\nSongs:`{len(self.playlist.songs)-1}`")
        self.embed.set_footer(text=f"Page: {1 if self.page_number < 0 else self.page_number+1} of {(len(self.playlist.songs)//10)+1}")


    def page_right(self, playlist: Playlist):
        self.page_number += 1
        self.update_embed(playlist)

    def page_left(self, playlist: Playlist):
        self.page_number -= 1
        self.update_embed(playlist)
class QueueView(ui.View):
    def __init__(self, queueEmbed: QueueEmbed, miku: MikuMusicCommands ,timeout: Optional[float] = 90):
        super().__init__(timeout=timeout)
        self.queueEmbed = queueEmbed
        self.page_right.disabled = len(self.queueEmbed.playlist.songs) <= 10
        self.button_shuffle.disabled = len(self.queueEmbed.playlist.songs) < 2
        self.miku = miku
        self.message: discord.Message|None = None
    # @discord.ui.select()
    # async def song_select(self, interaction: Interaction):
    #     pass

    @discord.ui.button(emoji="⬅️",style=discord.ButtonStyle.secondary, disabled=True)
    async def page_back(self, interaction: Interaction, button: ui.Button):
        g_id = interaction.guild_id
        if not g_id:
            return None
        gp_state = self.miku.guildpback_dict[g_id]
        self.queueEmbed.page_left(Playlist(gp_state.songs_list))
        if self.queueEmbed.page_number <= 0:
            button.disabled = True
        self.page_right.disabled = False
        await interaction.response.edit_message(embed=self.queueEmbed.embed, view=self)

    @discord.ui.button(emoji="➡️",style=discord.ButtonStyle.secondary, disabled=True)
    async def page_right(self, interaction: Interaction, button: ui.Button):
        g_id = interaction.guild_id
        if not g_id:
            return None
        gp_state = self.miku.guildpback_dict[g_id]
        self.queueEmbed.page_right(Playlist(gp_state.songs_list))
        if self.queueEmbed.page_number >= self.queueEmbed.max_pages:
            button.disabled = True
        self.page_back.disabled = False
        await interaction.response.edit_message(embed=self.queueEmbed.embed, view=self)


    @discord.ui.button(emoji="🔀",style=discord.ButtonStyle.secondary, disabled=False)
    async def button_shuffle(self, interaction: Interaction, button: ui.Button):
        await self.miku._shuffle_queue(interaction)
        g_id = interaction.guild_id or -1
        gp_state = self.miku.guildpback_dict.get(g_id)
        if not gp_state: return None
        self.queueEmbed.update_embed(Playlist(gp_state.songs_list))
        if self.message:
            await self.message.edit(embed=self.queueEmbed.embed)
        return None

    @discord.ui.button(emoji="<:WAPPLE:883418567654117426>",style=discord.ButtonStyle.danger, disabled=False)
    async def button_night_core(self, interaction: Interaction, button: ui.Button):
        g_id = interaction.guild_id or -1
        gp_state = self.miku.guildpback_dict.get(g_id)
        if not gp_state: return None
        await self.miku._night_core(interaction)
        self.queueEmbed.night_core = gp_state.nightcore
        self.queueEmbed.update_embed(Playlist(gp_state.songs_list))
        if self.message:
            await self.message.edit(embed=self.queueEmbed.embed)
        return None

    @discord.ui.button(label="STOP",style=discord.ButtonStyle.success, disabled=False)
    async def button_stop(self, interaction: Interaction, button: ui.Button):
        g_id = interaction.guild_id
        if not g_id:
            return None
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        await interaction.response.edit_message(view=self)
        await self.miku.guildpback_dict[g_id].voice_cleanup(leave_vc=True)

    async def on_timeout(self):
        if self.message:
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
            await self.message.edit(view=self)
        return None
