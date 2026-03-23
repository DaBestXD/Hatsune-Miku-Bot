import asyncio
import io
import logging
import time
import random
from collections.abc import Awaitable, Callable
from discord import Interaction
from discord.ext import commands
from audio_utils.audio_handler import get_Audio_Source
from audio_utils.bot_audio_functions import build_audio, mod_song
from botextras.bot_funcs_ext import reply, text_only_embed
from botextras.bot_events import (FinishedPlayback, ClearQueue, LoopSong,
    Nightcore, QueueSongs, RemoveFromQueue, SetBass, SetSpeed, Shuffle, Skip, GuildPlaybackState,
    Event, StopPlayblack, UpdateVoiceStatus, VolumeControl)
from botextras.constants import CACHE_TIMER_S

EventHandler = Callable[[Event], Awaitable[None]]

class GuildStateController():
    def __init__(self, bot: commands.Bot, id: int) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.id = id
        self.bot = bot
        self.queue:asyncio.Queue[Event] = asyncio.Queue()
        self.state = GuildPlaybackState()
        self.task: asyncio.Task|None = None
        self.event_handlers: dict[type[Event], EventHandler] = {
            QueueSongs: self._handle_queue_songs,
            Skip: self._skip,
            Shuffle: self._shuffle,
            Nightcore: self._nightcore,
            StopPlayblack: self._stop_playback,
            VolumeControl: self._change_volume,
            UpdateVoiceStatus: self._update_voice_status,
            RemoveFromQueue: self._remove_from_queue,
            LoopSong: self._loop_song,
            ClearQueue: self._clear_queue,
            FinishedPlayback: self._finished_playback,
            SetBass: self._setbass,
            SetSpeed: self._setspeed,
        }

    async def run(self):
        if self.task and not self.task.done():
            return
        self.task = asyncio.create_task(self.main_loop())

    async def stop(self):
        if not self.task:
            return None
        self.task.cancel()
        try:
            await self.task
        except asyncio.CancelledError:
            pass
        self.task = None

    async def add_event(self, event: Event):
        await self.queue.put(event)

    async def main_loop(self):
        while True:
            event = await self.queue.get()
            try:
                await self._handle_event(event)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.logger.exception("Failed handling %s for guild %s", type(event).__name__, self.id,)
                self._fail_event(event, exc)
            finally:
                self.queue.task_done()

    async def _handle_event(self, event: Event) -> None:
        handler = self.event_handlers.get(type(event))
        if not handler:
            self.logger.warning("Unknown event type: %s", type(event).__name__)
            return None
        await handler(event)
        return None

    def _fail_event(self, event: Event, exc: Exception) -> None:
        done = getattr(event, "done", None)
        self.logger.exception("%s", exc.__str__)
        if done and not done.done():
            done.set_exception(exc)
        return None

    # TODO fix later
    async def remove_from_cache(self, song_url: str):
        await asyncio.sleep(CACHE_TIMER_S)
        if song_url in self.state.song_cache:
            self.state.song_cache.pop(song_url)

    async def bad_cache(self):
        for s in self.state.songs[:3]:
            song = self.state.song_cache.get(s.webpage_url)
            if song: continue
            source = await get_Audio_Source((s.title,s.webpage_url))
            if not source: continue
            self.state.song_cache[s.webpage_url] = source
            asyncio.create_task(self.remove_from_cache(s.webpage_url))

    async def _change_volume(self, event: Event) -> None:
        if not isinstance(event, VolumeControl): return None
        self.state.volume = event.volume
        if self.state.source:
            self.state.source.volume = event.volume
        return None

    async def _clear_queue(self, event: Event) -> None:
        if not isinstance(event, ClearQueue): return None
        self.state.songs = []
        if self.state.active_song:
            self.state.songs.append(self.state.active_song)
        await reply(event.interaction,embed=text_only_embed("Queue cleared!"))
        return None

    async def _loop_song(self, event: Event):
        if not isinstance(event, LoopSong): return None
        self.state.song_loop = not event.loop
        text = "🔁Now looping current song!🔁" if self.state.song_loop else "No longer looping current song!"
        await reply(event.interaction,embed=text_only_embed(text))

    async def _remove_from_queue(self, event: Event) -> None:
        if not isinstance(event, RemoveFromQueue): return None
        try:
            if event.idx == 0:
                raise IndexError
            await reply(event.interaction, embed=text_only_embed(f"Removing {self.state.songs[event.idx].title} from the queue!"))
            self.state.songs.pop(event.idx)
        except IndexError:
            await reply(event.interaction, embed=text_only_embed("Value must be within queue"))
        return None

    async def _queue_helper(self, event: Event) -> None:
        if not isinstance(event, QueueSongs): return None
        self.state.songs.extend(event.songs)
        self.state.vc = event.vc
        self.state.active_song = self.state.songs[0]
        self.state.text_channel = event.text_channel
        next_song = self.state.songs[1] if len(self.state.songs) >= 2 else None
        if event.playlist:
            await reply(event.interaction,embed=event.playlist.return_embed())
        else:
            await reply(event.interaction,embed=event.songs[0].return_embed(next_song,queued=True))

    async def _handle_queue_songs(self, event: Event) -> None:
        if not isinstance(event, QueueSongs): return None
        await self._queue_helper(event)
        if not event.vc.is_playing():
            await self._play()
        return None

    async def _update_voice_status(self, event: Event) -> None:
        if not isinstance(event, UpdateVoiceStatus): return None
        self.state.vc = event.vc
        return None

    async def _play(self) -> None:
        song = self.state.active_song
        if song and self.state.vc:
            source = self.state.song_cache.get(song.webpage_url)
            if not source:
                source = await get_Audio_Source((song.title,song.webpage_url))
            if not source:
                if self.state.text_channel:
                    await self.state.text_channel.send(embed=self.state.songs[0].return_err_embed())
                self.state.songs.pop(0)
                self.state.active_song = self.state.songs[0] if self.state.songs else None
                return await self._play()
            stderr_buff = io.BytesIO()
            seek_time = self.state.seek_time if self.state.seek_time else 0
            # prob should change song_mods to be a class that builds one string
            song_mods = self.state.song_bass + self.state.song_pitch + self.state.song_speed
            built_source = await asyncio.to_thread(build_audio,
                                                   self.state.volume,
                                                   source,
                                                   stderr_buff,
                                                   seek_time,
                                                   song_mods)
            self.state.source = built_source
            self.state.vc.play(built_source, after= lambda error, stderr_buff=stderr_buff: self._callback_queue(error,stderr_buff))
            if not self.state.mod_song:
                self.state.start_time = time.monotonic()
                if self.state.text_channel:
                    next_song = self.state.songs[1] if len(self.state.songs) >= 2 else None
                    await self.state.text_channel.send(embed=song.return_embed(next_song))
            else:
                self.state.mod_song = False
                self.state.seek_time = None
            self.state.song_cache[song.webpage_url] = source
            await self.bad_cache()
        else:
            if self.state.text_channel:
                await self.state.text_channel.send(embed=text_only_embed("Queue empty🐱"))
        return None

    def _callback_queue(self, error: Exception | None, stderr_buff: io.BytesIO,) -> None:
        if error: ...
        ffmpeg_error = stderr_buff.getvalue().decode("utf-8", errors="ignore")
        asyncio.run_coroutine_threadsafe(self.add_event(FinishedPlayback(ffmpeg_error)),self.bot.loop)
        return None

    async def _finished_playback(self, event: Event) -> None:
        if not isinstance(event, FinishedPlayback): return None
        if "403 Forbidden" in event.ffmpeg_error:
            if self.state.active_song:
                try:
                    self.state.song_cache.pop(self.state.active_song.webpage_url)
                except: ...
        if self.state.songs:
            if not self.state.song_loop:
                self.state.songs.pop(0)
        self.state.active_song = self.state.songs[0] if self.state.songs else None
        await self._play()
        return None

    async def _skip(self, event: Event) -> None:
        if not isinstance(event, Skip): return None
        next_song = self.state.songs[1] if len(self.state.songs) >= 2 else None
        if self.state.active_song:
            await reply(event.interaction,embed=self.state.active_song.return_skip_embed(next_song))
        self.state.song_loop = False
        if self.state.vc:
            self.state.vc.stop()
        await self.bad_cache()
        return None

    async def _shuffle(self, event: Event) -> None:
        if not isinstance(event, Shuffle): return None
        await reply(event.interaction,embed=text_only_embed("🔀Queue shuffled🔀"))
        if self.state.songs and len(self.state.songs) > 2:
            head = [self.state.songs[0]]
            body = self.state.songs[1:] if len(self.state.songs) > 1 else []
            random.shuffle(body)
            self.state.songs = head + body
        if event.done and not event.done.done():
                event.done.set_result(None)
        await self.bad_cache()
        return None

    async def _song_mod_helper(self, interaction: Interaction, text: str) -> None:
        if self.state.vc and self.state.active_song:
            self.state.songs.insert(1,self.state.active_song)
            if self.state.start_time:
                self.state.seek_time = time.monotonic() - self.state.start_time
            self.state.vc.stop()
            await reply(interaction,embed=text_only_embed(text))
        return None

    async def _nightcore(self, event: Event) -> None:
        if not isinstance(event, Nightcore): return None
        self.state.song_pitch = await mod_song("pitch",1.25) if not self.state.song_pitch else await mod_song("off")
        self.state.mod_song = True
        text = "Nightcore on!🙀" if not self.state.nightcore else "Nightcore off!😿"
        self.state.nightcore = not self.state.nightcore
        await self._song_mod_helper(event.interaction, text)
        if event.done and not event.done.done():
            event.done.set_result(None)
        return None

    async def _setbass(self, event: Event) -> None:
        if not isinstance(event, SetBass): return None
        self.state.song_bass = await mod_song("bass",effect_strength=event.effect_strength)
        self.state.mod_song = True
        text = f"Bass set to {event.effect_strength}!"
        await self._song_mod_helper(event.interaction, text)
        return None

    async def _setspeed(self, event: Event) -> None:
        if not isinstance(event, SetSpeed): return None
        self.state.song_speed = await mod_song("speed",effect_strength=event.effect_strength)
        self.state.mod_song = True
        text = f"Speed set to {event.effect_strength}!"
        await self._song_mod_helper(event.interaction, text)
        return None

    async def _stop_playback(self, event: Event) -> None:
        if not isinstance(event, StopPlayblack): return None
        self.state.active_song = None
        self.state.seek_time = None
        self.state.text_channel = None
        self.state.start_time = None
        self.state.source = None
        self.state.nightcore = False
        self.state.song_loop = False
        self.state.mod_song = False
        self.state.song_pitch = ""
        self.state.song_bass = ""
        self.state.song_speed = ""
        self.state.songs = []
        if self.state.vc:
            if self.state.vc.is_playing():
                self.state.vc.stop()
            await self.state.vc.disconnect()
        self.state.vc = None
        await reply(event.interaction, embed=text_only_embed("Stopping playback..."))

    async def hard_reset(self) -> None:
        await self.stop()
        if self.state.vc:
            try:
                if self.state.vc.is_playing():
                    self.state.vc.stop()
            except Exception: pass
            try:
                await self.state.vc.disconnect()
            except Exception: pass
        self.state = GuildPlaybackState()
        self.queue = asyncio.Queue()
        await self.run()
