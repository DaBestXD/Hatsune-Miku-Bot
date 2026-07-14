import random
from dataclasses import dataclass, field
from hatsune_miku_bot.audio_utils.bot_audio_functions import build_audio
import io
from hatsune_miku_bot.audio_utils.audio_handler import get_Audio_Source
from hatsune_miku_bot.botextras.bot_funcs_ext import reply, text_only_embed
from discord import Interaction, VoiceClient, TextChannel, PCMVolumeTransformer
from hatsune_miku_bot.audio_utils.audio_class import Song, Playlist
from typing import Any, ParamSpec, Literal
from collections.abc import Callable, Coroutine
import asyncio
import logging
from discord.ext import commands

logger = logging.getLogger(__name__)
P = ParamSpec("P")


class GuildStateController:
    def __init__(self, bot: commands.Bot, id: int) -> None:
        self.id = id
        self.bot = bot
        self.queue: asyncio.Queue[Event] = asyncio.Queue()
        self.state = GuildPlaybackState()
        self.task: asyncio.Task | None = None

    async def _stop_event(self):
        """
        Sentinel event for exiting the event loop
        """
        return None

    async def add_event(
        self,
        func: Callable[P, Coroutine[Any, Any, None]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        async def func_to_execute() -> None:
            await func(*args, **kwargs)

        await self.queue.put(Event(func_to_execute))

    async def run(self) -> None:
        if self.task and not self.task.done():
            return None
        self.task = asyncio.create_task(
            self.main_loop(),
            name=f"Main queue loop for {self.id}  created",
        )
        logger.debug("Main queue loop for %d created", self.id)

    async def main_loop(self):
        while True:
            event = await self.queue.get()
            if event == self._stop_event:
                logger.debug("Stop event recieved, breaking loop")
                break
            try:
                await event.func_to_execute()
            except Exception:
                logger.exception(
                    "Failed handling %s for guild %s",
                    type(event).__name__,
                    self.id,
                )
            finally:
                self.queue.task_done()

    async def queue_songs(
        self, interaction: Interaction, item_to_add: Song | Playlist, vc: VoiceClient
    ) -> None:
        """
        TODO: DOCSTRING
        """
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
            next_song = self.state.songs[1] if len(self.state.songs) >= 2 else None
            await reply(
                interaction, embed=item_to_add.return_embed(next_song, queued=True)
            )

    async def begin_playback(self) -> None:
        if not self.state.vc:
            logger.warning("Attempted to play song while not in vc")
            return None
        self.state.active_song = self.state.songs[0] if self.state.songs else None
        if not self.state.active_song:
            logger.warning("Attempted to play song with no active song set")
            return None
        if self.state.vc.is_playing():
            logger.debug("Already playing, queueing songs...")
            return None
        source = await get_Audio_Source(self.state.active_song)
        if not source:
            if self.state.text_channel:
                await self.state.text_channel.send(
                    embed=self.state.songs[0].return_err_embed()
                )
            self.state.songs.pop(0)
            self.state.active_song = self.state.songs[0] if self.state.songs else None
            return None
        stderr_buff = io.BytesIO()
        built_source = await asyncio.to_thread(
            build_audio,
            self.state.songMods.volume,
            source,
            stderr_buff,
            0.0,  # TODO: add back seek_time later
            self.state.songMods.combined_song_mods,
        )
        self.state.source = built_source
        self.state.vc.play(
            built_source,
            after=lambda error: self.after_callback(error, stderr_buff),
        )
        if self.state.text_channel:
            next_song = self.state.songs[1] if len(self.state.songs) >= 2 else None
            await self.state.text_channel.send(
                embed=self.state.active_song.return_embed(next_song)
            )
        else:
            logger.warning(
                "No text channel was set for %s", self.begin_playback.__name__
            )

    def after_callback(self, error: Exception | None, stderr_buff: io.BytesIO) -> None:
        if error:
            logger.error("%s", error)
        ffmpeg_error = stderr_buff.getvalue().decode("utf-8", errors="ignore")
        asyncio.run_coroutine_threadsafe(
            self.add_event(self.finished_playback, ffmpeg_error), self.bot.loop
        )
        return None

    async def finished_playback(self, ffmpeg_error: str):
        if "403 Forbidden" in ffmpeg_error:
            # TODO: add cache removal
            pass
        if not self.state.songMods.song_loop and self.state.songs:
            self.state.songs.pop(0)
        self.state.active_song = self.state.songs[0] if self.state.songs else None
        if not self.state.active_song:
            if not self.state.text_channel:
                logger.warning(
                    "Text channel was none for %s", self.finished_playback.__name__
                )
                return None
            await self.state.text_channel.send(embed=text_only_embed("Queue empty🐱"))
            return None
        else:
            await self.add_event(self.begin_playback)

    async def skip(self, interaction: Interaction) -> None:
        next_song = self.state.songs[1] if len(self.state.songs) >= 2 else None
        if self.state.active_song:
            await reply(
                interaction,
                embed=self.state.active_song.return_skip_embed(next_song),
            )
        self.state.songMods.song_loop = False
        if self.state.vc:
            self.state.vc.stop()
        # TODO:
        # await self.bad_cache()
        return None

    async def stop_playback(self, interaction: Interaction) -> None:
        self.state.songMods.reset_all_values()
        if self.state.vc:
            if self.state.vc.is_playing():
                self.state.vc.stop()
            await self.state.vc.disconnect()
        self.state.vc = None
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
        # TODO:
        # await self.bad_cache()


@dataclass
class Event:
    func_to_execute: Callable[[], Coroutine[Any, Any, None]]


class SongMods:
    def __init__(self):
        self.song_bass: float | None = None
        self.song_loop: bool = False
        self.song_loop_all: bool = False
        self.song_speed: float | None = None
        self.song_pitch: float | None = None
        self.start_time: float | None = None
        self.seek_time: float | None = None
        self.position_offset_s: float = 0.0
        self.volume: float = 1.0

    @property
    def is_nightcore(self) -> bool:
        """
        Nightcore is equivalent to pitch=1.25
        """
        return True if self.song_pitch == 1.25 else False

    @property
    def is_song_mods_on(self) -> bool:
        if self.song_bass:
            return True
        if self.song_speed:
            return True
        if self.song_pitch:
            return True
        return False

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
        self.start_time: float | None = None
        self.seek_time: float | None = None
        self.position_offset_s: float = 0.0
        self.volume: float = 1.0


@dataclass
class GuildPlaybackState:
    active_song: Song | None = None
    songs: list[Song] = field(default_factory=list)
    song_cache: dict[str, str] = field(default_factory=dict)
    songMods: SongMods = SongMods()
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
        return f",aresample=48000,asetrate=48000*{effect_strength},aresample=48000"
    if mod_type == "speed":
        return f",atempo={effect_strength}"
    if mod_type == "bass":
        return f",bass=g={effect_strength}"
    if mod_type == "off":
        return ""
