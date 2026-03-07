from __future__ import annotations
import time
import discord
from botextras.constants import INVIS_CHAR, ASSET_DIR


class Song():
    def __init__(self, title:str, webpage_url:str, thumbnail_url:str, duration:str, view_count:str) -> None:
        self.title:str = title
        self.webpage_url:str = webpage_url
        self.thumbnail_url:str = thumbnail_url
        try:
            self.duration = int(float(duration))
            self.formatted_duration = time.strftime("%M:%S",time.gmtime(self.duration))
        except ValueError:
            self.duration = 0
            self.formatted_duration = 0
        self.view_count:str = view_count

    def return_embed(self, next_song: Song|None = None, queued: bool = False, char_limit: int = 45) -> discord.Embed:
        author_title = "Song added to queue:" if queued else "Now playing:"
        embed = discord.Embed(title=self.title,url=self.webpage_url,description=f"Song length: `{self.formatted_duration}`")
        embed.set_author(name=author_title)
        embed.set_thumbnail(url=self.thumbnail_url)
        if next_song:
            embed.set_footer(text=f"Next song: {next_song.title[:char_limit]} ({next_song.formatted_duration})")
        else:
            embed.set_footer(text=f"End of queue.")
        return embed

    def return_err_embed(self) -> discord.Embed:
        embed = discord.Embed(title=self.title,url=self.webpage_url,description=f"Song length {self.formatted_duration}")
        embed.set_author(name="Error trying to play:")
        embed.set_thumbnail(url=self.thumbnail_url)
        embed.set_footer(text="Skipping...")
        return embed

    def return_skip_embed(self, next_song: Song|None = None, char_limit: int = 45) -> discord.Embed:
        safe_title = self.title.replace("[","【").replace("]","】")[:char_limit]
        footer_text: str = f"Next song: {next_song.title[:char_limit]}" if next_song else "End of queue."
        embed = discord.Embed(title=safe_title,url=self.webpage_url,description=f"Song length: `{self.formatted_duration}`")
        embed.set_author(name="Skipping...")
        embed.set_thumbnail(url=self.thumbnail_url)
        embed.set_footer(text=footer_text)
        return embed

    def __str__(self) -> str:
        var_list = [f"{k} : {v}" for k,v in self.__dict__.items()]
        return "\n".join(var_list)


class Playlist():
    def __init__(self, songs: list[Song], playlist_title: str = "Default", playlist_url: str = "None",playlist_thumbnail: str = "None") -> None:
        if not songs:
            raise ValueError("Songs cannot be none")
        self.playlist_title = playlist_title
        self.playlist_url = playlist_url
        self.playlist_thumbnail = playlist_thumbnail
        self.songs:list[Song] = songs
        self.length = len(songs)
        self.total_duration:int = sum([s.duration for s in self.songs])
        self.formatted_duration = time.strftime("%H:%M:%S",time.gmtime(self.total_duration))

    def return_embed(self) -> discord.Embed:
        embed = discord.Embed(title=self.playlist_title,url=self.playlist_url,description=f"Playlist length: `{self.formatted_duration}`")
        embed.set_author(name=f"Added {self.length} songs to the queue")
        embed.set_thumbnail(url=self.playlist_thumbnail)
        return embed

    def return_err_embed(self) -> discord.Embed:
        embed = discord.Embed(title=self.playlist_title, url=self.playlist_url,description=f"Playlist length `{self.formatted_duration}`")
        embed.set_author(name="Error trying to play:")
        embed.set_thumbnail(url=self.playlist_thumbnail)
        embed.set_footer(text="Skipping...")
        return embed

    def return_queue_embed(self, char_limit: int = 45) -> tuple[discord.Embed,discord.File]:
        embed = discord.Embed()
        body_text:list[str] = []
        img_path = ASSET_DIR / "hatsuneplush.jpg"
        image_file = discord.File(img_path, filename="hatsuneplush.jpg")
        embed.set_thumbnail(url="attachment://hatsuneplush.jpg")
        if len(self.songs) <= 1:
            body_text.append("End of queue.")
        for idx,s in enumerate(self.songs[:11]):
            safe_title = s.title.replace("[","【").replace("]","】")[:char_limit]
            if len(safe_title) >= char_limit:
                safe_title += "..."
            if idx == 0:
                embed.add_field(name="Currently playing:",value=f"[{safe_title}]({s.webpage_url}) `{s.formatted_duration}`",inline=False)
            else:
                body_text.append(f"{idx}. [{safe_title}]({s.webpage_url}) `{s.formatted_duration}`")
        embed.add_field(name="Song queue:",value="\n".join(body_text))
        return embed, image_file

    def greatest_view_count(self) -> Song|None:
        if self.songs:
            _,song = max([(int(s.view_count),s) for s in self.songs if s.view_count.isnumeric()])
            return song
        else:
            return None

    def return_song_info(self, idx: int)->Song|None:
        if not self.songs:
            raise ValueError(f"No songs in playlist: {self.__class__.__name__}")
        try:
            return self.songs[idx]
        except IndexError:
            raise IndexError(f"Index out of bounds for playlist: {self.__class__.__name__}")

    def __str__(self) -> str:
        return f"""Playlist title: {self.playlist_title}\nPlaylist url: {self.playlist_url}\nPlaylist length: {self.length}\nPlaylist thumbnail: {self.playlist_thumbnail}\nTotal duration: {self.formatted_duration} """

