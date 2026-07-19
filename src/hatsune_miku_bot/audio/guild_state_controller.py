import asyncio
import io
import logging
import random
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any, Literal

from discord import Interaction, PCMVolumeTransformer, TextChannel, VoiceClient
from discord.ext import commands

from hatsune_miku_bot.audio.audio_resolver import get_audio_source
from hatsune_miku_bot.audio.playback_helpers import build_audio
from hatsune_miku_bot.audio.song_playlist_classes import Playlist, Song
from hatsune_miku_bot.db_logging.db_main import DBLogic
from hatsune_miku_bot.utils.discord_helpers import reply, text_only_embed

logger = logging.getLogger(__name__)


class GuildStateController:
    def __init__(self, bot: commands.Bot, id: int, db_logic: DBLogic) -> None:
        self.id = id
        self.bot = bot
        self.queue: asyncio.Queue[Event | StopEvent] = asyncio.Queue()
        self.state = GuildPlaybackState()
        self.task: asyncio.Task | None = None
        self.db_logic = db_logic

    async def add_event[**P](
        self,
        func: Callable[P, Coroutine[Any, Any, None]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        async def func_to_execute() -> None:
            await func(*args, **kwargs)

        await self.queue.put(Event(func_to_execute))

    async def stop(self) -> None:
        if not self.task or self.task.done():
            return None
        await self.queue.put(StopEvent())
        await self.task
        self.task = None

    async def run(self) -> None:
        if self.task and not self.task.done():
            logger.debug("Main queue loop already running")
            return None
        self.task = asyncio.create_task(
            self.main_loop(),
            name=f"Main queue loop for {self.id}  created",
        )
        logger.debug("Main queue loop for %d created", self.id)

    async def main_loop(self) -> None:
        while True:
            event = await self.queue.get()
            try:
                if isinstance(event, StopEvent):
                    logger.debug("Stop event recieved, breaking loop")
                    break
                await event.func_to_execute()
            except Exception:
                logger.exception(
                    "Failed handling %s for guild %s",
                    type(event).__name__,
                    self.id,
                )
            finally:
                self.queue.task_done()

    async def remove_song_from_cache(self, song_url: str) -> None:
        try:
            logger.debug("Removed %s from song cache", song_url)
            self.state.song_cache.pop(song_url)
        except KeyError:
            logger.warning("%s was missing from cache already", song_url)
        return None

    async def schedule_removal_from_cache(
        self, song_url: str, time_until_removal: float = 1800
    ) -> None:
        logger.debug("Removing %s in %d seconds", song_url, time_until_removal)
        await asyncio.sleep(time_until_removal)
        await self.add_event(self.remove_song_from_cache, song_url)

    async def cache_song(self, song: Song) -> None:
        source = await get_audio_source(song)
        if not source:
            logger.warning(
                "Failed to cache audio for %s[%s]", song.title, song.webpage_url
            )
            return None
        logger.debug("Caching %s[%s]", song.title, song.webpage_url)
        self.state.song_cache[song.webpage_url] = source

    async def begin_song_cache(self) -> None:
        """
        Cache the first 3 songs in the queue
        """
        for s in self.state.songs[:3]:
            song = self.state.song_cache.get(s.webpage_url)
            if song:
                continue
            await self.add_event(self.cache_song, s)
            asyncio.create_task(self.schedule_removal_from_cache(s.webpage_url))  # noqa: RUF006

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
            next_song = (
                self.state.songs[1] if len(self.state.songs) >= 2 else None
            )
            await reply(
                interaction,
                embed=item_to_add.return_embed(next_song, queued=True),
            )
        await self.add_event(self.begin_song_cache)

    # TODO: DOCSTRING
    async def begin_playback(self) -> None:
        if not self.state.vc:
            logger.warning("Attempted to play song while not in vc")
            return None
        self.state.active_song = (
            self.state.songs[0] if self.state.songs else None
        )
        if not self.state.active_song:
            logger.warning("Attempted to play song with no active song set")
            return None
        if self.state.vc.is_playing():
            # Debug message here too noisy, will fire on skip/queue events, etc.
            return None
        source = self.state.song_cache.get(self.state.active_song.webpage_url)
        if not source:
            logger.debug("Cache miss, fetching source using ydl")
            source = await get_audio_source(self.state.active_song)
            if source:
                song = self.state.active_song
                logger.debug("Caching %s[%s]", song.title, song.webpage_url)
                self.state.song_cache[self.state.active_song.webpage_url] = (
                    source
                )
        if not source:
            # Error branch if source cannot be found
            logger.warning(
                "No source found for %s", self.state.active_song.title
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
                    "No text channel was set for erorr branch in %s",
                    self.begin_playback.__name__,
                )
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
        self.state.vc.play(
            built_source,
            after=lambda error: self.after_callback(error, stderr_buff),
        )
        if self.state.song_mods.is_song_modified:
            self.state.song_mods.is_song_modified = False
            return None
        else:
            await self.db_logic.insert_song_playback(
                self.state.active_song, self.id
            )
        if self.state.text_channel:
            next_song = (
                self.state.songs[1] if len(self.state.songs) >= 2 else None
            )
            await self.state.text_channel.send(
                embed=self.state.active_song.return_embed(next_song)
            )
        else:
            logger.warning(
                "No text channel was set for %s", self.begin_playback.__name__
            )
        await self.add_event(self.begin_playback)

    def after_callback(
        self, error: Exception | None, stderr_buff: io.BytesIO
    ) -> None:
        if error:
            logger.error("%s", error)
        ffmpeg_error = stderr_buff.getvalue().decode("utf-8", errors="ignore")
        asyncio.run_coroutine_threadsafe(
            self.add_event(self.finished_playback, ffmpeg_error), self.bot.loop
        )
        return None

    async def finished_playback(self, ffmpeg_error: str) -> None:
        if ffmpeg_error:
            logger.debug("%s", ffmpeg_error)
        if "403 Forbidden" in ffmpeg_error:
            await self.recover_stale_audio_source()
            return None
        if not self.state.song_mods.is_song_modified:
            self.state.song_mods.start_timestamp = None
            self.state.song_mods.position_offset_s = 0
        if self.state.song_mods.song_loop_all:
            if self.state.active_song:
                if not self.state.song_mods.is_song_modified:
                    self.state.songs.append(self.state.active_song)
                self.state.songs.pop(0)
            else:
                logger.warning("Doing song loop all no active song was found")
        elif not self.state.song_mods.song_loop and self.state.songs:
            self.state.songs.pop(0)
        self.state.active_song = (
            self.state.songs[0] if self.state.songs else None
        )
        if not self.state.active_song:
            if not self.state.text_channel:
                logger.warning(
                    "Text channel was none for %s",
                    self.finished_playback.__name__,
                )
                return None
            await self.state.text_channel.send(
                embed=text_only_embed("Queue empty🐱")
            )
            return None
        else:
            await self.add_event(self.begin_playback)
            return None

    async def recover_stale_audio_source(self) -> None:
        active_song = self.state.active_song
        if not active_song:
            logger.warning("403 error while no active song set")
            return None
        self.state.song_cache.pop(active_song.webpage_url, None)
        self.state.song_mods.start_timestamp = None
        self.state.song_mods.position_offset_s = 0
        if not self.state.songs or self.state.songs[0] is not active_song:
            self.state.songs.insert(0, active_song)
        self.state.active_song = active_song
        await self.add_event(self.begin_playback)
        return None

    async def skip(self, interaction: Interaction) -> None:
        next_song = self.state.songs[1] if len(self.state.songs) >= 2 else None
        if self.state.active_song:
            await reply(
                interaction,
                embed=self.state.active_song.return_skip_embed(next_song),
            )
        self.state.song_mods.song_loop = False
        if self.state.vc:
            self.state.vc.stop()
        else:
            logger.warning("Skip was called while not in vc")
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
        self.state.song_mods.is_song_modified = True
        if self.state.vc and self.state.active_song:
            # Steps to modify song insert copy of song into queue
            if not self.state.song_mods.song_loop:
                self.state.songs.insert(1, self.state.active_song)
            self.state.vc.stop()
        else:
            logger.warning("Attempted to modify song without an active song")
        await reply(interaction, embed=text_only_embed(embed_text))

    async def nightcore(self, interaction: Interaction) -> None:
        self.state.song_mods.position_offset_s = (
            self.state.song_mods.interrupt_time()
        )
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
        self.state.song_mods.position_offset_s = (
            self.state.song_mods.interrupt_time()
        )
        self.state.song_mods.song_bass = effect_strength
        await self._modify_song_playback(
            interaction, f"Bass set to {effect_strength}"
        )
        return None

    async def set_speed(
        self, interaction: Interaction, effect_strength: float
    ) -> None:
        self.state.song_mods.position_offset_s = (
            self.state.song_mods.interrupt_time()
        )
        self.state.song_mods.song_speed = effect_strength
        await self._modify_song_playback(
            interaction, f"Speed set to {effect_strength}"
        )
        return None


@dataclass
class StopEvent:
    """
    Sentinel event to stop the event loop
    """


@dataclass
class Event:
    """
    Fields:
        `func_to_execute: Callable[[], Coroutine[Any, Any, None]]`
    """

    func_to_execute: Callable[[], Coroutine[Any, Any, None]]


class SongMods:
    def __init__(self):
        self.is_song_modified: bool = False
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
            logger.warning("Start timestamp was not found")
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
        self.is_song_modified = False


@dataclass
class GuildPlaybackState:
    active_song: Song | None = None
    songs: list[Song] = field(default_factory=list)
    song_cache: dict[str, str] = field(default_factory=dict)
    """
    Key is webpage_url, value is the source
    """
    song_mods: SongMods = field(default_factory=SongMods)
    source: PCMVolumeTransformer | None = None
    text_channel: TextChannel | None = None
    vc: VoiceClient | None = None


def _song_mod_to_ffmpeg_str(
    mod_type: Literal["pitch", "speed", "bass", "off"],
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
    if mod_type == "off":
        return ""
