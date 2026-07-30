import asyncio
import io
import logging
import random
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

import aiosqlite
from discord import (
    FFmpegPCMAudio,
    Interaction,
    PCMVolumeTransformer,
    TextChannel,
    VoiceClient,
)
from discord.ext import commands

from hatsune_miku_bot.audio.audio_resolver import get_audio_source
from hatsune_miku_bot.audio.playback_helpers import build_audio
from hatsune_miku_bot.audio.song_cache import CachedSong, SongCache
from hatsune_miku_bot.audio.song_playlist_classes import Playlist, Song
from hatsune_miku_bot.db_logging.db_main import (
    DBLogic,
    PlaylistSongRemovalStatus,
)
from hatsune_miku_bot.monitoring.factory import DisabledMonitor, Monitor
from hatsune_miku_bot.utils.discord_helpers import reply, text_only_embed

logger = logging.getLogger(__name__)


class _PlaybackType(StrEnum):
    MODIFIED_RESTART = "modified_restart"
    STALE_RESTART = "stale_restart"
    NEW_SONG = "new_song"


class _PlaybackResult(StrEnum):
    ACTIVE_SONG_MISSING = "active_song_missing"
    CALLBACK_ERROR = "callback_error"
    ENDED = "ended"
    MODIFIER_RESTART_REQUESTED = "modifier_restart_requested"
    SOURCE_MISSING = "source_missing"
    STALE_SOURCE_DETECTED = "stale_source_detected"
    START_ERROR = "start_error"
    STARTED = "started"
    VOICE_CLIENT_MISSING = "voice_client_missing"


class _EventResult(StrEnum):
    COMPLETED = "completed"
    EXCEPTION = "exception"


class GuildStateController:
    def __init__(
        self,
        bot: commands.Bot,
        id: int,
        db_logic: DBLogic,
        monitor: Monitor | None = None,
    ) -> None:
        self.id = id
        self.bot = bot
        self.queue: asyncio.Queue[Event | StopEvent] = asyncio.Queue()
        self.state = GuildPlaybackState()
        self.song_cache = SongCache()
        self.task: asyncio.Task[None] | None = None
        self.db_logic = db_logic
        self.monitor = monitor if monitor else DisabledMonitor()

    async def add_event[**P](
        self,
        func: Callable[P, Coroutine[Any, Any, Any]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        async def func_to_execute() -> None:
            await func(*args, **kwargs)

        await self.queue.put(
            Event(
                name=getattr(func, "__name__", type(func).__name__),
                func_to_execute=func_to_execute,
            )
        )

    async def stop(self) -> None:
        if not self.task or self.task.done():
            return None
        await self.queue.put(StopEvent())
        await self.task
        self.task = None

    async def run(self) -> None:
        if self.task and not self.task.done():
            logger.debug(
                "Guild event loop is already running",
                extra={
                    "event": "guild_event_loop_already_running",
                    "guild_id": self.id,
                },
            )
            return None
        self.task = asyncio.create_task(
            self.main_loop(),
            name=f"Main queue loop for {self.id}  created",
        )
        logger.debug(
            "Guild event loop started",
            extra={
                "event": "guild_event_loop_started",
                "guild_id": self.id,
            },
        )

    async def main_loop(self) -> None:
        while True:
            event = await self.queue.get()
            started_at = time.perf_counter()
            result = _EventResult.COMPLETED
            try:
                if isinstance(event, StopEvent):
                    logger.debug(
                        "Guild event loop received stop event",
                        extra={
                            "event": "guild_event_loop_stopping",
                            "guild_id": self.id,
                        },
                    )
                    break
                await event.func_to_execute()
            except Exception:
                result = _EventResult.EXCEPTION
                logger.exception(
                    "Guild event loop failed to process %s",
                    event.name,
                    extra={
                        "event": "guild_event_processing_failed",
                        "guild_id": self.id,
                    },
                )
            finally:
                self.monitor.observe_event(
                    event=event.name,
                    result=result.value,
                    duration=time.perf_counter() - started_at,
                )
                self.queue.task_done()

    async def cache_song(self, song: Song) -> None:
        source = await get_audio_source(song)
        if not source:
            logger.warning(
                "Failed to cache audio for %s[%s]",
                song.title,
                song.webpage_url,
                extra={
                    "event": "song_cache_failed",
                    "guild_id": self.id,
                },
            )
            return None
        logger.debug(
            "Caching audio for %s[%s]",
            song.title,
            song.webpage_url,
            extra={
                "event": "song_cache_started",
                "guild_id": self.id,
            },
        )
        await self.song_cache.add_key(song.webpage_url, CachedSong(source))

    async def begin_song_cache(self) -> None:
        """
        Cache the first 3 songs in the queue
        """
        for s in self.state.songs[:3]:
            song = await self.song_cache.get(s.webpage_url)
            if song:
                continue
            await self.add_event(self.cache_song, s)

    # TODO: DOCSTRING
    async def queue_songs(
        self,
        interaction: Interaction,
        item_to_add: Song | Playlist,
        vc: VoiceClient,
    ) -> None:
        self.state.vc = vc
        if isinstance(interaction.channel, TextChannel):
            self.state.text_channel = interaction.channel
        else:
            self.state.text_channel = None
        if isinstance(item_to_add, Playlist):
            self.state.songs.extend(item_to_add.songs)
            await reply(interaction, embed=item_to_add.return_embed())
        else:
            self.state.songs.append(item_to_add)
            await reply(
                interaction,
                embed=item_to_add.return_embed(
                    self.state.next_song, queued=True
                ),
            )
        await self.add_event(self.begin_song_cache)

    async def _missing_source_helper(self) -> None:
        if not self.state.active_song:
            logger.warning(
                "No audio source was found without an active song",
                extra={
                    "event": "playback_source_missing",
                    "guild_id": self.id,
                },
            )
        else:
            logger.warning(
                "No audio source was found for %s",
                self.state.active_song.title,
                extra={
                    "event": "playback_source_missing",
                    "guild_id": self.id,
                },
            )
        if self.state.text_channel:
            await self.state.text_channel.send(
                embed=self.state.songs[0].return_err_embed()
            )
        self.state.songs.pop(0)
        self.state.active_song = (
            self.state.songs[0] if self.state.songs else None
        )
        if self.state.active_song:
            await self.add_event(self.begin_playback)
        elif self.state.text_channel:
            await self.state.text_channel.send(
                embed=text_only_embed("Queue empty🐱")
            )
        else:
            logger.debug(
                "No text channel was available for the playback error",
                extra={
                    "event": "playback_error_text_channel_missing",
                    "guild_id": self.id,
                },
            )
        return None

    # TODO: DOCSTRING
    async def begin_playback(
        self, playback_type: _PlaybackType = _PlaybackType.NEW_SONG
    ) -> None:
        if not self.state.vc:
            self.monitor.observe_playback(
                playback_type,
                _PlaybackResult.VOICE_CLIENT_MISSING,
            )
            logger.warning(
                "Playback requested without a voice client",
                extra={
                    "event": "playback_voice_client_missing",
                    "guild_id": self.id,
                    "playback_type": playback_type.name,
                },
            )
            return None
        self.state.active_song = (
            self.state.songs[0] if self.state.songs else None
        )
        if not self.state.active_song:
            self.monitor.observe_playback(
                playback_type,
                _PlaybackResult.ACTIVE_SONG_MISSING,
            )
            logger.warning(
                "Playback requested without an active song",
                extra={
                    "event": "playback_active_song_missing",
                    "guild_id": self.id,
                    "playback_type": playback_type.name,
                },
            )
            return None
        if self.state.vc.is_playing():
            # Debug message here too noisy, will fire on skip/queue events, etc.
            return None
        await self.song_cache.clear_expired_songs()
        source = await self.song_cache.get(self.state.active_song.webpage_url)
        if not source:
            # Cache check branch
            logger.debug(
                "Audio cache miss; resolving source",
                extra={
                    "event": "song_cache_miss",
                    "guild_id": self.id,
                    "playback_type": playback_type.name,
                },
            )
            source = await get_audio_source(self.state.active_song)
            if source:
                await self.song_cache.add_key(
                    self.state.active_song.webpage_url, CachedSong(source)
                )
        if not source:
            self.monitor.observe_playback(
                playback_type,
                _PlaybackResult.SOURCE_MISSING,
            )
            await self._missing_source_helper()
            return None
        stderr_buff = io.BytesIO()
        built_source = await asyncio.to_thread(
            build_audio,
            self.state.song_mods.volume,
            source,
            stderr_buff,
            self.state.song_mods.position_offset_s,
            self.state.song_mods.combined_song_mods,
        )
        self.state.source = built_source
        self.state.song_mods.start_timestamp = time.monotonic()
        try:
            self.state.vc.play(
                built_source,
                after=lambda error: self.after_callback(
                    error, stderr_buff, playback_type
                ),
            )
        except Exception:
            self.monitor.observe_playback(
                playback_type,
                _PlaybackResult.START_ERROR,
            )
            raise
        self.monitor.observe_playback(playback_type, _PlaybackResult.STARTED)
        if playback_type is _PlaybackType.MODIFIED_RESTART:
            self.state.song_mods.modifier_restart_pending = False
            return None
        if playback_type is _PlaybackType.NEW_SONG:
            await self.db_logic.insert_song_playback(
                self.state.active_song, self.id
            )
            if self.state.text_channel:
                await self.state.text_channel.send(
                    embed=self.state.active_song.return_embed(
                        self.state.next_song
                    )
                )
            else:
                logger.warning(
                    "No text channel was set for playback",
                    extra={
                        "event": "playback_text_channel_missing",
                        "guild_id": self.id,
                        "playback_type": playback_type.name,
                    },
                )
        if playback_type is _PlaybackType.STALE_RESTART:
            logger.debug(
                "Recovered playback from a stale cached source",
                extra={
                    "event": "playback_stale_source_recovered",
                    "guild_id": self.id,
                    "playback_type": playback_type.name,
                },
            )

    def after_callback(
        self,
        error: Exception | None,
        stderr_buff: io.BytesIO,
        playback_type: _PlaybackType,
    ) -> None:
        if error:
            logger.error(
                "Voice playback callback reported an error: %s",
                error,
                exc_info=(type(error), error, error.__traceback__),
                extra={
                    "event": "playback_callback_failed",
                    "guild_id": self.id,
                    "playback_type": playback_type.name,
                    "exception": str(error),
                },
            )
        ffmpeg_error = stderr_buff.getvalue().decode("utf-8", errors="ignore")
        asyncio.run_coroutine_threadsafe(
            self.add_event(
                self.finished_playback,
                ffmpeg_error,
                playback_type,
                error is not None,
            ),
            self.bot.loop,
        )
        return None

    async def finished_playback(
        self,
        ffmpeg_error: str,
        playback_type: _PlaybackType = _PlaybackType.NEW_SONG,
        callback_failed: bool = False,
    ) -> None:
        if ffmpeg_error:
            logger.debug(
                "FFmpeg playback diagnostics: %s",
                ffmpeg_error,
                extra={
                    "event": "ffmpeg_playback_diagnostics",
                    "guild_id": self.id,
                    "playback_type": playback_type.name,
                },
            )
        if "403 Forbidden" in ffmpeg_error:
            self.monitor.observe_playback(
                playback_type,
                _PlaybackResult.STALE_SOURCE_DETECTED,
            )
            await self.recover_stale_audio_source(playback_type)
            return None
        if self.state.song_mods.modifier_restart_pending:
            self.monitor.observe_playback(
                playback_type,
                _PlaybackResult.MODIFIER_RESTART_REQUESTED,
            )
            await self.add_event(
                self.begin_playback,
                playback_type=_PlaybackType.MODIFIED_RESTART,
            )
            return None
        self.monitor.observe_playback(
            playback_type,
            (
                _PlaybackResult.CALLBACK_ERROR
                if callback_failed
                else _PlaybackResult.ENDED
            ),
        )
        self.state.song_mods.start_timestamp = None
        self.state.song_mods.position_offset_s = 0
        if self.state.song_mods.song_loop_all:
            if self.state.active_song:
                self.state.songs.append(self.state.active_song)
                self.state.songs.pop(0)
            else:
                logger.warning(
                    "Queue looping expected an active song",
                    extra={
                        "event": "playback_loop_active_song_missing",
                        "guild_id": self.id,
                        "playback_type": playback_type.name,
                    },
                )
        elif not self.state.song_mods.song_loop and self.state.songs:
            self.state.songs.pop(0)
        self.state.active_song = (
            self.state.songs[0] if self.state.songs else None
        )
        if not self.state.active_song:
            if not self.state.text_channel:
                logger.warning(
                    "No text channel was available after playback finished",
                    extra={
                        "event": "playback_text_channel_missing",
                        "guild_id": self.id,
                        "playback_type": playback_type.name,
                    },
                )
                return None
            await self.state.text_channel.send(
                embed=text_only_embed("Queue empty🐱")
            )
            return None
        else:
            await self.add_event(self.begin_playback)
            return None

    async def recover_stale_audio_source(
        self, failed_playback_type: _PlaybackType
    ) -> None:
        active_song = self.state.active_song
        if not active_song:
            logger.warning(
                "Stale source recovery requested without an active song",
                extra={
                    "event": "playback_stale_source_active_song_missing",
                    "guild_id": self.id,
                    "playback_type": failed_playback_type.name,
                },
            )
            return None
        preserve_modifier_position = (
            failed_playback_type is _PlaybackType.MODIFIED_RESTART
            or self.state.song_mods.modifier_restart_pending
        )
        await self.song_cache.delete_key(active_song.webpage_url)
        if not preserve_modifier_position:
            self.state.song_mods.start_timestamp = None
            self.state.song_mods.position_offset_s = 0
        if not self.state.songs or self.state.songs[0] is not active_song:
            self.state.songs.insert(0, active_song)
        self.state.active_song = active_song
        playback_type = (
            _PlaybackType.MODIFIED_RESTART
            if preserve_modifier_position
            else _PlaybackType.STALE_RESTART
        )
        await self.add_event(self.begin_playback, playback_type=playback_type)
        return None

    async def skip(self, interaction: Interaction) -> None:
        if self.state.active_song:
            await reply(
                interaction,
                embed=self.state.active_song.return_skip_embed(
                    self.state.next_song
                ),
            )
        self.state.song_mods.song_loop = False
        self.state.song_mods.modifier_restart_pending = False
        if self.state.vc:
            self.state.vc.stop()
        else:
            logger.warning(
                "Skip requested without a voice client",
                extra={
                    "event": "playback_skip_voice_client_missing",
                    "guild_id": self.id,
                },
            )
        await self.add_event(self.begin_song_cache)
        return None

    async def stop_playback(self, interaction: Interaction) -> None:
        self.state.song_mods.reset_all_values()
        if self.state.vc:
            if self.state.vc.is_playing():
                self.state.vc.stop()
            await self.state.vc.disconnect()
        self.state.vc = None
        self.state.source = None
        self.state.songs = []
        self.state.text_channel = None
        self.state.active_song = None
        await reply(interaction, embed=text_only_embed("Stopping playback..."))

    async def shuffle(self, interaction: Interaction) -> None:
        await reply(interaction, embed=text_only_embed("🔀Queue shuffled🔀"))
        if self.state.songs and len(self.state.songs) > 2:
            head = [self.state.songs[0]]
            body = self.state.songs[1:] if len(self.state.songs) > 1 else []
            random.shuffle(body)
            self.state.songs = head + body
        await self.add_event(self.begin_song_cache)

    async def change_volume(self, new_volume: float) -> None:
        self.state.song_mods.volume = new_volume
        if self.state.source:
            self.state.source.volume = new_volume
        return None

    async def clear_queue(self, interaction: Interaction) -> None:
        self.state.songs = []
        if self.state.active_song:
            self.state.songs.append(self.state.active_song)
        await reply(interaction, embed=text_only_embed("Queue cleared!"))
        return None

    async def loop_song(self, interaction: Interaction):
        self.state.song_mods.song_loop_all = False
        self.state.song_mods.song_loop = not self.state.song_mods.song_loop
        text = (
            "🔁Now looping current song!🔁"
            if self.state.song_mods.song_loop
            else "No longer looping current song!"
        )
        await reply(interaction, embed=text_only_embed(text))

    async def loop_all(self, interaction: Interaction) -> None:
        self.state.song_mods.song_loop = False
        self.state.song_mods.song_loop_all = (
            not self.state.song_mods.song_loop_all
        )
        text = (
            "🔁Now looping queue!🔁"
            if self.state.song_mods.song_loop_all
            else "No longer looping queue!"
        )
        await reply(interaction, embed=text_only_embed(text))

    async def remove_from_queue(
        self, interaction: Interaction, idx_to_remove: int
    ) -> None:
        try:
            if idx_to_remove == 0:
                raise IndexError
            await reply(
                interaction,
                embed=text_only_embed(
                    f"Removing {self.state.songs[idx_to_remove].title} from the queue!"  # noqa: E501
                ),
            )
            self.state.songs.pop(idx_to_remove)
        except IndexError:
            await reply(
                interaction, embed=text_only_embed("Value must be within queue")
            )
        return None

    async def _modify_song_playback(
        self, interaction: Interaction, embed_text: str
    ) -> None:
        await reply(interaction, embed=text_only_embed(embed_text))

    def _request_modifier_restart(self) -> None:
        if self.state.song_mods.modifier_restart_pending:
            return None
        if not self.state.vc or not self.state.active_song:
            logger.warning(
                "Playback modifier requested without an active song",
                extra={
                    "event": "playback_modifier_active_song_missing",
                    "guild_id": self.id,
                },
            )
            return None
        self.state.song_mods.position_offset_s = (
            self.state.song_mods.interrupt_time()
        )
        self.state.song_mods.start_timestamp = None
        self.state.song_mods.modifier_restart_pending = True
        self.state.vc.stop()
        return None

    async def nightcore(self, interaction: Interaction) -> None:
        self._request_modifier_restart()
        if self.state.song_mods.is_nightcore():
            self.state.song_mods.song_pitch = None
            text = "Nightcore off!😿"
        else:
            self.state.song_mods.song_pitch = 1.25
            text = "Nightcore on!🙀"
        await self._modify_song_playback(interaction, text)
        return None

    async def set_bass(
        self, interaction: Interaction, effect_strength: float
    ) -> None:
        self._request_modifier_restart()
        self.state.song_mods.song_bass = effect_strength
        await self._modify_song_playback(
            interaction, f"Bass set to {effect_strength}"
        )
        return None

    async def set_speed(
        self, interaction: Interaction, effect_strength: float
    ) -> None:
        self._request_modifier_restart()
        self.state.song_mods.song_speed = effect_strength
        await self._modify_song_playback(
            interaction, f"Speed set to {effect_strength}"
        )
        return None

    # TODO: add logging
    async def create_custom_playlist(
        self, interaction: Interaction, playlist_name: str
    ) -> None:
        try:
            created = await self.db_logic.create_custom_playlist(
                interaction, playlist_name
            )
            if created:
                await reply(
                    interaction,
                    embed=text_only_embed(f"Created {playlist_name}!"),
                )
            else:
                await reply(
                    interaction,
                    embed=text_only_embed(f"{playlist_name} already exists!"),
                )
        except aiosqlite.Error:
            await reply(
                interaction,
                embed=text_only_embed(
                    "Error occured doing playlist creation try again!"
                ),
            )

    async def add_song_to_custom_playlist(
        self,
        interaction: Interaction,
        playlist_name: str,
        song: Song | Playlist,
    ) -> None:
        try:
            added = await self.db_logic.add_song_to_playlist(
                interaction,
                playlist_name,
                song,
            )
            if added:
                await reply(
                    interaction,
                    embed=song.add_song_to_custom_playlist(
                        playlist_name, added
                    ),
                )
            else:
                await reply(
                    interaction,
                    embed=song.add_song_to_custom_playlist(
                        playlist_name, added
                    ),
                )
        except aiosqlite.Error:
            await reply(
                interaction,
                embed=text_only_embed(
                    "Error occurred adding song to playlist, try again!"
                ),
            )

    async def remove_song_from_custom_playlist(
        self,
        interaction: Interaction,
        playlist_name: str,
        song_identifier: str | None,
    ) -> str | None:
        try:
            removal_result = await self.db_logic.remove_song_from_playlist(
                interaction,
                playlist_name,
                song_identifier,
            )
            if (
                removal_result.status is PlaylistSongRemovalStatus.REMOVED
                and removal_result.title is not None
            ):
                removed_title = removal_result.title
                await reply(
                    interaction,
                    embed=text_only_embed(
                        f"Removed {removed_title} from {playlist_name}!"
                    ),
                )
                return removed_title
            if (
                removal_result.status
                is PlaylistSongRemovalStatus.AMBIGUOUS_TITLE
            ):
                await reply(
                    interaction,
                    embed=text_only_embed(
                        f"Multiple songs named {song_identifier} were found in "
                        f"{playlist_name}. Select an autocomplete option or "
                        "enter the song URL."
                    ),
                )
                return None
            await reply(
                interaction,
                embed=text_only_embed(
                    f"Song was not found in {playlist_name}!"
                ),
            )
        except aiosqlite.Error:
            await reply(
                interaction,
                embed=text_only_embed(
                    "Error occurred removing song from playlist, try again!"
                ),
            )
        return None

    async def delete_custom_playlist(
        self,
        interaction: Interaction,
        playlist_name: str,
    ) -> None:
        try:
            deleted = await self.db_logic.delete_custom_playlist(
                interaction,
                playlist_name,
            )
            if deleted:
                await reply(
                    interaction,
                    embed=text_only_embed(f"Deleted {playlist_name}!"),
                )
            else:
                await reply(
                    interaction,
                    embed=text_only_embed(f"{playlist_name} was not found!"),
                )
        except aiosqlite.Error:
            await reply(
                interaction,
                embed=text_only_embed(
                    "Error occurred deleting playlist, try again!"
                ),
            )

    async def play_custom_playlist(
        self,
        interaction: Interaction,
        playlist_name: str,
        vc: VoiceClient,
    ) -> list[Song]:
        try:
            songs = await self.db_logic.get_playlist_songs(
                interaction,
                playlist_name,
            )
        except aiosqlite.Error:
            await reply(
                interaction,
                embed=text_only_embed(
                    "Error occurred loading playlist, try again!"
                ),
            )
            return []

        if not songs:
            await reply(
                interaction,
                embed=text_only_embed(f"{playlist_name} is empty or missing!"),
            )
            return []
        playlist = Playlist(
            songs,
            playlist_title=f"Custom Playlist: {playlist_name}",
            playlist_thumbnail=songs[0].thumbnail_url,
        )
        await self.queue_songs(interaction, playlist, vc)
        await self.add_event(self.begin_playback)
        return songs


@dataclass
class StopEvent:
    """
    Sentinel event to stop the event loop
    """

    name: str = "StopEvent"


@dataclass
class Event:
    """
    Fields:
        `name: Event name used for logs and monitoring`
        `func_to_execute: Callable[[], Coroutine[Any, Any, None]]`
    """

    name: str
    func_to_execute: Callable[[], Coroutine[Any, Any, None]]


class SongMods:
    def __init__(self):
        self.modifier_restart_pending: bool = False
        self.song_bass: float | None = None
        self.song_loop: bool = False
        self.song_loop_all: bool = False
        self.song_speed: float | None = None
        self.song_pitch: float | None = None
        self.start_timestamp: float | None = None
        self.position_offset_s: float = 0
        self.volume: float = 1.0

    @property
    def effective_playback_rate(self) -> float:
        rate: float = 1.0
        if self.song_speed:
            rate *= self.song_speed
        if self.song_pitch:
            rate *= self.song_pitch
        return rate

    def is_nightcore(self) -> bool:
        """
        Nightcore is equivalent to pitch=1.25
        """
        return self.song_pitch == 1.25

    def interrupt_time(self) -> float:
        if self.start_timestamp is None:
            logger.warning(
                "Playback modifier position requested without start timestamp",
                extra={"event": "playback_start_timestamp_missing"},
            )
            return self.position_offset_s

        elapsed = time.monotonic() - self.start_timestamp
        return self.position_offset_s + (elapsed * self.effective_playback_rate)

    @property
    def is_song_mods_on(self) -> bool:
        """
        Currently not used but will probably used later,
        for song embed information
        """
        if self.song_bass:
            return True
        if self.song_speed:
            return True
        return bool(self.song_pitch)

    @property
    def combined_song_mods(self) -> str:
        """
        Return a string ready for ffmpeg of all the current song mods
        """
        combined_str = ""
        if self.song_bass:
            combined_str += _song_mod_to_ffmpeg_str("bass", self.song_bass)
        if self.song_speed:
            combined_str += _song_mod_to_ffmpeg_str("speed", self.song_speed)
        if self.song_pitch:
            combined_str += _song_mod_to_ffmpeg_str("pitch", self.song_pitch)
        return combined_str

    def reset_all_values(self) -> None:
        """
        Reset all class attributes to none or default values
        """
        self.song_bass: float | None = None
        self.song_loop: bool = False
        self.song_loop_all: bool = False
        self.song_speed: float | None = None
        self.song_pitch: float | None = None
        self.start_timestamp: float | None = None
        self.position_offset_s: float = 0.0
        self.volume: float = 1.0
        self.modifier_restart_pending = False


@dataclass
class GuildPlaybackState:
    active_song: Song | None = None
    songs: list[Song] = field(default_factory=list)
    song_mods: SongMods = field(default_factory=SongMods)
    source: PCMVolumeTransformer[FFmpegPCMAudio] | None = None
    text_channel: TextChannel | None = None
    vc: VoiceClient | None = None

    @property
    def next_song(self) -> Song | None:
        return self.songs[1] if len(self.songs) > 1 else None


def _song_mod_to_ffmpeg_str(
    mod_type: Literal["pitch", "speed", "bass"],
    effect_strength: float,
) -> str:
    """
    Build an str ready for ffmpeg song mod options
    """
    if mod_type == "pitch":
        return (
            f",aresample=48000,asetrate=48000*{effect_strength},aresample=48000"
        )
    if mod_type == "speed":
        return f",atempo={effect_strength}"
    if mod_type == "bass":
        return f",bass=g={effect_strength}"
