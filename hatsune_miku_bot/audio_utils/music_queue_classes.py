from __future__ import annotations
import asyncio
import discord
from typing import Optional, TYPE_CHECKING
from discord import Color, Interaction, VoiceClient, ui
from audio_utils.audio_class import Playlist
from audio_utils.bot_audio_functions import join_vc
from audio_utils.guildstate_controller import GuildStateController
from botextras.bot_events import Nightcore, Shuffle, StopPlayblack
from botextras.constants import DIS_BOT_THUMBNAIL, INVIS_CHAR

if TYPE_CHECKING:
    from cogs.musicplayer import MikuMusicCommands

class QueueEmbed():
    def __init__(self, gp_con: GuildStateController) -> None:
        self.page_number = 0
        self.playlist = Playlist(gp_con.state.songs)
        self.max_pages = 0
        self.embed: discord.Embed|None = None
        self.update_embed(gp_con)

    def update_embed(self, gp_con: GuildStateController):
        queued_songs = gp_con.state.songs[1:]
        queued_song_count = len(queued_songs)
        self.max_pages = ((queued_song_count - 1) // 10) if queued_song_count else 0
        if self.page_number > self.max_pages:
            self.page_number = self.max_pages
        if self.page_number < 0:
            self.page_number = 0
        if active_song := gp_con.state.active_song:
            truncated_title:str = active_song.title[:30]
            if len(truncated_title) >= 30: truncated_title += "..."
            truncated_title += f" ({gp_con.state.active_song.formatted_duration})"
            if not self.embed:
                self.embed = discord.Embed(title=truncated_title,url=active_song.webpage_url,color=Color.blue())
                self.embed.set_thumbnail(url=DIS_BOT_THUMBNAIL)
                self.embed.set_author(name="Currently playing:")
            else:
                self.embed.title = truncated_title
                self.embed.url = active_song.webpage_url
                self.embed.clear_fields()
            start = self.page_number * 10
            page_slice = queued_songs[start:start + 10]
            body_text: list[str] = []
            if queued_songs:
                for idx, s in enumerate(page_slice, start=start + 1):
                    safe_title = s.title.replace("[","【").replace("]","】")[:25]
                    if len(safe_title) >= 25: safe_title += "..."
                    body_text.append(f"{idx}. [{safe_title}]({s.webpage_url}) `{s.formatted_duration}`")
                self.embed.add_field(name="Song queue:",value="\n".join(body_text),inline=False)
            else:
                self.embed.add_field(name="Song queue:",value="Queue empty!",inline=False)
            human_night = "Enabled" if gp_con.state.nightcore else "Disabled"
            human_loop = "Enabled" if gp_con.state.song_loop else "Disabled"
            human_speed = "Default" if not gp_con.state.song_speed else gp_con.state.song_speed.replace(",atempo=","")
            human_bass = "Default" if not (b:=gp_con.state.song_bass.replace(",bass=g=","")) else b
            playlist = Playlist(gp_con.state.songs)
            self.embed.add_field(name=f"Queue details:",value=f"Looping:`{human_loop}`\nDuration:`{playlist.formatted_duration}`")
            self.embed.add_field(name=INVIS_CHAR,value=f"Nightcore:`{human_night}`\nSongs:`{len(playlist.songs)-1}`")
            self.embed.add_field(name=INVIS_CHAR,value=f"Speed:`{human_speed}`\nBass:`{human_bass}`")
            self.embed.set_footer(text=f"Page: {self.page_number + 1} of {self.max_pages + 1}")


    def page_right(self, gp_con: GuildStateController):
        self.page_number += 1
        self.update_embed(gp_con)

    def page_left(self, gp_con: GuildStateController):
        self.page_number -= 1
        self.update_embed(gp_con)

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
        if not (g_id := interaction.guild_id): return None
        gp_con = await self.miku.return_gp_con(g_id)
        self.queueEmbed.page_left(gp_con)
        if self.queueEmbed.page_number <= 0:
            button.disabled = True
        self.page_right.disabled = False
        await interaction.response.edit_message(embed=self.queueEmbed.embed, view=self)

    @discord.ui.button(emoji="➡️",style=discord.ButtonStyle.secondary, disabled=True)
    async def page_right(self, interaction: Interaction, button: ui.Button):
        if not (g_id := interaction.guild_id): return None
        gp_con = await self.miku.return_gp_con(g_id)
        self.queueEmbed.page_right(gp_con)
        if self.queueEmbed.page_number >= self.queueEmbed.max_pages:
            button.disabled = True
        self.page_back.disabled = False
        await interaction.response.edit_message(embed=self.queueEmbed.embed, view=self)


    @discord.ui.button(emoji="🔀",style=discord.ButtonStyle.secondary, disabled=False)
    async def button_shuffle(self, interaction: Interaction, button: ui.Button):
        if not (g_id := interaction.guild_id): return None
        await interaction.response.defer()
        gp_con = await self.miku.return_gp_con(g_id)
        done = asyncio.get_running_loop().create_future()
        await gp_con.add_event(Shuffle(interaction,done))
        await done
        self.queueEmbed.update_embed(gp_con)
        if self.message:
            await self.message.edit(embed=self.queueEmbed.embed)
        return None

    @discord.ui.button(emoji="<:WAPPLE:883418567654117426>",style=discord.ButtonStyle.danger, disabled=False)
    async def button_night_core(self, interaction: Interaction, button: ui.Button):
        if not (g_id := interaction.guild_id): return None
        await interaction.response.defer()
        if (vc := await join_vc(interaction,join=False)) and isinstance(vc, VoiceClient):
            gp_con = await self.miku.return_gp_con(g_id)
            done = asyncio.get_running_loop().create_future()
            await gp_con.add_event(Nightcore(interaction,vc,done=done))
            await done
            self.queueEmbed.update_embed(gp_con)
            if self.message:
                await self.message.edit(embed=self.queueEmbed.embed)
        return None

    @discord.ui.button(label="STOP",style=discord.ButtonStyle.success, disabled=False)
    async def button_stop(self, interaction: Interaction, button: ui.Button):
        if not (g_id := interaction.guild_id): return None
        await interaction.response.defer()
        gp_con = await self.miku.return_gp_con(g_id)
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        if self.message:
            await self.message.edit(view=self)
        await gp_con.add_event(StopPlayblack(interaction))

    async def on_timeout(self):
        if self.message:
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
            await self.message.edit(view=self)
        return None
