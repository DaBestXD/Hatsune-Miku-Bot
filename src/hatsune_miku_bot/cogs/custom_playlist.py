# TODO: FIX LATER, impl is still a little messy
from discord import Interaction, VoiceClient, app_commands

from hatsune_miku_bot.audio.audio_resolver import AudioInfoResolver
from hatsune_miku_bot.audio.guild_state_controller import (
    GuildStateController,
)
from hatsune_miku_bot.audio.playback_helpers import join_vc
from hatsune_miku_bot.db_logging.db_main import DBLogic
from hatsune_miku_bot.utils.discord_helpers import reply, text_only_embed


class CustomPlaylistCommands:
    """Custom-playlist commands mixed into the music cog."""

    audio_info_resolver: AudioInfoResolver | None
    db_logic: DBLogic
    guildstate_con_dict: dict[int, GuildStateController]

    custom_playlist = app_commands.Group(
        name="custom-playlist",
        description="Create, edit, and play custom playlists",
        guild_only=True,
    )

    @custom_playlist.command(
        name="add-song",
        description="Add a song or playlist to the custom playlist",
    )
    async def add_song_to_custom_playlist(
        self, interaction: Interaction, playlist_name: str, source: str
    ) -> None:
        await interaction.response.defer()
        if not (guild_id := interaction.guild_id):
            return None
        audio_resolver = self.audio_info_resolver
        if not audio_resolver:
            # TODO: logging event
            return None
        result = await audio_resolver.get_song_info(source)
        if not result:
            await reply(
                interaction,
                embed=text_only_embed(f"Error trying to add {source}"),
            )
            return None
        gp_con = self.guildstate_con_dict[guild_id]
        await gp_con.add_event(
            gp_con.add_song_to_custom_playlist,
            interaction,
            playlist_name,
            result,
        )
        return None

    @add_song_to_custom_playlist.autocomplete("playlist_name")
    async def add_song_to_custom_playlist_autocomplete(
        self, interaction: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.playlist_names_autocomplete(interaction, current)

    @custom_playlist.command(
        name="remove-song",
        description="Remove a song from the playlist",
    )
    async def remove_song_from_custom_playlist(
        self,
        interaction: Interaction,
        playlist_name: str,
        song_name: str,
    ) -> None:
        await interaction.response.defer()
        if not (guild_id := interaction.guild_id):
            return None
        gp_con = self.guildstate_con_dict[guild_id]
        await gp_con.add_event(
            gp_con.remove_song_from_custom_playlist,
            interaction,
            playlist_name,
            song_name,
        )
        return None

    @remove_song_from_custom_playlist.autocomplete("playlist_name")
    async def remove_playlist_name_autocomplete(
        self, interaction: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.playlist_names_autocomplete(interaction, current)

    @remove_song_from_custom_playlist.autocomplete("song_name")
    async def remove_song_name_autocomplete(
        self, interaction: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        playlist_name = getattr(interaction.namespace, "playlist_name", None)
        if not isinstance(playlist_name, str) or not playlist_name:
            return []
        songs = await self.db_logic.get_playlist_songs(
            interaction, playlist_name
        )
        normalized_current = current.casefold()
        choices: list[app_commands.Choice[str]] = []
        for song in songs:
            if not song.webpage_url:
                continue
            if song.webpage_url == current:
                return [
                    app_commands.Choice(
                        name=song.title[:100], value=song.webpage_url
                    )
                ]
            if normalized_current in song.title.casefold():
                choices.append(
                    app_commands.Choice(
                        name=f"{song.title[:90]}({song.duration})",
                        value=song.webpage_url,
                    )
                )
            if len(choices) == 25:
                break
        return choices

    @custom_playlist.command(
        name="play",
        description="Play a custom playlist",
    )
    async def play_custom_playlist(
        self,
        interaction: Interaction,
        playlist_name: str,
    ) -> None:
        await interaction.response.defer()
        if not (guild_id := interaction.guild_id):
            return None
        if not isinstance(vc := await join_vc(interaction), VoiceClient):
            return None
        gp_con = self.guildstate_con_dict[guild_id]
        await gp_con.add_event(
            gp_con.play_custom_playlist,
            interaction,
            playlist_name,
            vc,
        )
        return None

    @play_custom_playlist.autocomplete("playlist_name")
    async def play_custom_playlist_autocomplete(
        self, interaction: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.playlist_names_autocomplete(interaction, current)

    @custom_playlist.command(
        name="delete-playlist",
        description="Delete a custom playlist",
    )
    async def delete_custom_playlist(
        self,
        interaction: Interaction,
        playlist_name: str,
    ) -> None:
        await interaction.response.defer()
        if not (guild_id := interaction.guild_id):
            return None
        gp_con = self.guildstate_con_dict[guild_id]
        await gp_con.add_event(
            gp_con.delete_custom_playlist,
            interaction,
            playlist_name,
        )
        return None

    @delete_custom_playlist.autocomplete("playlist_name")
    async def delete_custom_playlist_autocomplete(
        self, interaction: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.playlist_names_autocomplete(interaction, current)

    async def playlist_names_autocomplete(
        self, interaction: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        playlists = await self.db_logic.fetch_playlist_names(interaction)
        normalized_current = current.casefold()
        matching_playlists = sorted(
            (
                playlist
                for playlist in playlists
                if normalized_current in playlist.casefold()
            ),
            key=str.casefold,
        )
        return [
            app_commands.Choice(name=playlist, value=playlist)
            for playlist in matching_playlists[:25]
        ]

    @custom_playlist.command(
        name="create-playlist",
        description="Create a custom playlist",
    )
    async def create_custom_playlist(
        self,
        interaction: Interaction,
        playlist_name: str,
    ) -> None:
        await interaction.response.defer()
        if not (guild_id := interaction.guild_id):
            return None
        gp_con = self.guildstate_con_dict[guild_id]
        await gp_con.add_event(
            gp_con.create_custom_playlist,
            interaction,
            playlist_name,
        )
        return None
