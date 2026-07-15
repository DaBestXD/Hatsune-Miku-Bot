from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Iterable, Self

import discord

if TYPE_CHECKING:
    from yt_dlp.extractor.common import _InfoDict
else:
    _InfoDict = dict[str, Any]


class Song:
    def __init__(
        self,
        title: str,
        webpage_url: str,
        thumbnail_url: str,
        duration: str,
        view_count: str,
    ) -> None:
        self.title: str = title
        self.webpage_url: str = webpage_url
        self.thumbnail_url: str = thumbnail_url
        try:
            self.duration = int(float(duration))
            if self.duration < 3600:
                self.formatted_duration = time.strftime(
                    "%M:%S", time.gmtime(self.duration)
                )
            else:
                self.formatted_duration = time.strftime(
                    "%H:%M:%S", time.gmtime(self.duration)
                )
        except ValueError:
            self.duration = 0
            self.formatted_duration = "0"
        self.view_count: str = view_count
        self.source = ""

    @classmethod
    def from_spotify(
        cls,
        json_reponse: dict[str, Any],
        album_thumbnail: str,
    ) -> Self:
        if album_thumbnail:
            song_name = json_reponse["name"]
            duration = json_reponse["duration_ms"] // 1000
            artist = json_reponse["artists"][0]["name"]
            spotify_url = json_reponse["external_urls"]["spotify"]
        else:
            song_name = json_reponse["name"]
            spotify_url = json_reponse["external_urls"]["spotify"]
            artist = json_reponse["artists"][0]["name"]
            album_thumbnail = json_reponse["album"]["images"][0]["url"]
            duration = json_reponse["duration_ms"] // 1000
        title = song_name + " - " + artist
        return cls(title, spotify_url, album_thumbnail, duration, "0")

    @classmethod
    def from_yt_dlp(cls, _info_dict: _InfoDict) -> Self:
        # TODO: this whole string situation needs to change
        thumbnails = _info_dict.get("thumbnails")
        thumbnail_url = ""
        # if not used here to exclude both empty lists and none values
        if thumbnails and isinstance(thumbnails, list):
            thumbnail_url = thumbnails[-1]["url"]
        return cls(
            title=str(_info_dict.get("title")),
            webpage_url=str(_info_dict.get("url")),
            thumbnail_url=thumbnail_url,
            duration=str(_info_dict.get("duration")),
            view_count=str(_info_dict.get("view_count")),
        )

    def return_embed(
        self,
        next_song: Song | None = None,
        queued: bool = False,
        char_limit: int = 30,
    ) -> discord.Embed:
        author_title = "Song added to queue:" if queued else "Now playing:"
        safe_title = self.title[:char_limit]
        if len(safe_title) >= char_limit:
            safe_title += "..."
        embed = discord.Embed(
            title=safe_title,
            url=self.webpage_url,
            description=f"Song length: `{self.formatted_duration}`",
            color=discord.Color.blue(),
        )
        embed.set_author(name=author_title)
        embed.set_thumbnail(url=self.thumbnail_url)
        if next_song:
            footer_title = next_song.title[:char_limit]
            if len(footer_title) >= char_limit:
                footer_title += "..."
            embed.set_footer(text=f"Next song: {footer_title}")
        else:
            embed.set_footer(text="Next song: None")
        return embed

    def return_err_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=self.title,
            url=self.webpage_url,
            description=f"Song length {self.formatted_duration}",
            color=discord.Color.blue(),
        )
        embed.set_author(name="Error trying to play:")
        embed.set_thumbnail(url=self.thumbnail_url)
        embed.set_footer(text="Skipping...")
        return embed

    def return_skip_embed(
        self, next_song: Song | None = None, char_limit: int = 30
    ) -> discord.Embed:
        safe_title = self.title.replace("[", "【").replace("]", "】")[
            :char_limit
        ]
        if len(safe_title) >= char_limit:
            safe_title += "..."
        footer_text: str = (
            f"Next song: {next_song.title[:char_limit]}"
            if next_song
            else "Next song: None"
        )
        embed = discord.Embed(
            title=safe_title,
            url=self.webpage_url,
            description=f"Song length: `{self.formatted_duration}`",
            color=discord.Color.blue(),
        )
        embed.set_author(name="Skipping...")
        embed.set_thumbnail(url=self.thumbnail_url)
        embed.set_footer(text=footer_text)
        return embed

    def __str__(self) -> str:
        var_list = [f"{k} : {v}" for k, v in self.__dict__.items()]
        return "\n".join(var_list)


class Playlist:
    def __init__(
        self,
        songs: list[Song],
        playlist_title: str = "Default",
        playlist_url: str = "None",
        playlist_thumbnail: str = "None",
    ) -> None:
        if not songs:
            raise ValueError("Songs cannot be none for a playlist")
        self.playlist_title = playlist_title
        self.playlist_url = playlist_url
        self.playlist_thumbnail = playlist_thumbnail
        self.songs: list[Song] = songs
        self.length = len(songs)
        self.total_duration: int = sum([s.duration for s in self.songs])
        self.formatted_duration = time.strftime(
            "%H:%M:%S", time.gmtime(self.total_duration)
        )

    @classmethod
    def from_spotify(
        cls,
        spotify_link: str,
        json_metadata_response: dict[str, Any],
        json_songs_response: dict[str, Any],
        is_album: bool,
    ) -> Self:
        # Two different json responses one for playlist / album information
        if is_album:
            playlist_name = json_metadata_response["name"]
            thumbnail_url = json_metadata_response["images"][0]["url"]
            album_thumbnail = thumbnail_url
        else:
            playlist_name = json_metadata_response["name"]
            thumbnail_url = json_metadata_response["images"][0]["url"]
            album_thumbnail = ""
        songs: list[Song] = []
        for item in json_songs_response["items"]:
            song_json = item if is_album else item.get("track")
            if song_json:
                songs.append(Song.from_spotify(song_json, album_thumbnail))
        return cls(songs, playlist_name, spotify_link, thumbnail_url)

    @classmethod
    def from_yt_dlp(
        cls, result: _InfoDict, entries: Iterable[_InfoDict]
    ) -> Self:
        songs = [Song.from_yt_dlp(e) for e in entries if e]
        thumbnails = result.get("thumbnails")
        thumbnail_url = ""
        # if not used here to exclude both empty lists and none values
        if thumbnails and isinstance(thumbnails, list):
            thumbnail_url = thumbnails[-1]["url"]
        return cls(
            songs,
            str(result.get("title")),
            str(result.get("original_url")),
            thumbnail_url,
        )

    def return_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=self.playlist_title,
            url=self.playlist_url,
            description=f"Playlist length: `{self.formatted_duration}`",
            color=discord.Color.blue(),
        )
        embed.set_author(name=f"Added {self.length} songs to the queue")
        embed.set_thumbnail(url=self.playlist_thumbnail)
        return embed

    def return_err_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=self.playlist_title,
            url=self.playlist_url,
            description=f"Playlist length `{self.formatted_duration}`",
            color=discord.Color.blue(),
        )
        embed.set_author(name="Error trying to play:")
        embed.set_thumbnail(url=self.playlist_thumbnail)
        embed.set_footer(text="Skipping...")
        return embed

    def greatest_view_count(self) -> Song | None:
        valid_songs = [
            s
            for s in self.songs
            if s.view_count and str(s.view_count).isnumeric()
        ]
        if not valid_songs:
            return None
        return max(valid_songs, key=lambda s: int(s.view_count))

    def return_song_info(self, idx: int) -> Song | None:
        if not self.songs:
            raise ValueError(f"No songs in playlist: {self.__class__.__name__}")
        try:
            return self.songs[idx]
        except IndexError:
            raise IndexError(
                f"Index out of bounds for playlist: {self.__class__.__name__}"
            )

    def __str__(self) -> str:
        return f"""Playlist title: {self.playlist_title}\nPlaylist url: {self.playlist_url}\nPlaylist length: {self.length}\nPlaylist thumbnail: {self.playlist_thumbnail}\nTotal duration: {self.formatted_duration} """  # noqa: E501
